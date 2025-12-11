"""Tests for svg_tools.align module."""

import math
import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES, find_group_by_label
from svg_tools.geometry import RectInfo, ArcInfo
from svg_tools.align import (
    GridRule,
    SizeRule,
    ArcRule,
    GroupRule,
    ToleranceConfig,
    AlignmentRule,
    Issue,
    ValidationResult,
    GroupValidationResult,
    AlignmentReport,
    parse_rule_file,
    iter_shapes_in_group,
    validate_rect,
    validate_arc,
    validate_shape,
    fix_rect,
    fix_arc,
    validate_and_fix_group,
    validate_svg,
    format_report,
    DEFAULT_TOLERANCE,
    DEFAULT_ERROR_THRESHOLD,
    DEFAULT_ARC_END,
)


class TestDataclasses:
    """Tests for configuration dataclasses."""

    def test_grid_rule(self):
        rule = GridRule(x=1.27, y=2.54)
        assert rule.x == 1.27
        assert rule.y == 2.54

    def test_size_rule(self):
        rule = SizeRule(width=10, height=20)
        assert rule.width == 10
        assert rule.height == 20

    def test_arc_rule_defaults(self):
        rule = ArcRule()
        assert rule.start == 0
        assert rule.end == pytest.approx(2 * math.pi)

    def test_tolerance_config_defaults(self):
        config = ToleranceConfig()
        assert config.acceptable == DEFAULT_TOLERANCE
        assert config.error_threshold == DEFAULT_ERROR_THRESHOLD


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_empty_result_is_ok(self):
        result = ValidationResult(element_id="test", shape_type="rect")
        assert result.is_ok is True
        assert result.has_errors is False
        assert result.has_fixable is False

    def test_result_with_ok_issues(self):
        result = ValidationResult(
            element_id="test",
            shape_type="rect",
            issues=[
                Issue(
                    element_id="test",
                    field="width",
                    status="ok",
                    actual=1.27,
                    expected=1.27,
                    deviation=0,
                    message="ok",
                )
            ],
        )
        assert result.is_ok is True

    def test_result_with_fixable(self):
        result = ValidationResult(
            element_id="test",
            shape_type="rect",
            issues=[
                Issue(
                    element_id="test",
                    field="width",
                    status="fixable",
                    actual=1.28,
                    expected=1.27,
                    deviation=0.01,
                    message="fixable",
                )
            ],
        )
        assert result.is_ok is False
        assert result.has_fixable is True
        assert result.has_errors is False

    def test_result_with_error(self):
        result = ValidationResult(
            element_id="test",
            shape_type="rect",
            issues=[
                Issue(
                    element_id="test",
                    field="width",
                    status="error",
                    actual=2.0,
                    expected=1.27,
                    deviation=0.73,
                    message="error",
                )
            ],
        )
        assert result.is_ok is False
        assert result.has_errors is True


class TestGroupValidationResult:
    """Tests for GroupValidationResult dataclass."""

    def test_empty_group(self):
        result = GroupValidationResult(group_name="test", shape_type="rect")
        assert result.has_errors is False
        assert result.error_count == 0
        assert result.fixable_count == 0
        assert result.ok_count == 0

    def test_group_with_mixed_results(self):
        ok_result = ValidationResult(element_id="ok", shape_type="rect")
        fixable_result = ValidationResult(
            element_id="fixable",
            shape_type="rect",
            issues=[
                Issue("fixable", "x", "fixable", 1.0, 1.27, 0.27, "msg")
            ],
        )
        error_result = ValidationResult(
            element_id="error",
            shape_type="rect",
            issues=[
                Issue("error", "x", "error", 5.0, 1.27, 3.73, "msg")
            ],
        )

        result = GroupValidationResult(
            group_name="test",
            shape_type="rect",
            element_results=[ok_result, fixable_result, error_result],
        )
        assert result.has_errors is True
        assert result.error_count == 1
        assert result.fixable_count == 1
        assert result.ok_count == 1


class TestAlignmentReport:
    """Tests for AlignmentReport dataclass."""

    def test_empty_report(self):
        report = AlignmentReport(file_path=Path("test.svg"))
        assert report.has_errors is False
        assert report.total_elements == 0
        assert report.total_errors == 0
        assert report.total_fixable == 0

    def test_report_with_groups(self):
        group1 = GroupValidationResult(
            group_name="g1",
            shape_type="rect",
            element_results=[
                ValidationResult(element_id="e1", shape_type="rect"),
                ValidationResult(element_id="e2", shape_type="rect"),
            ],
        )
        group2 = GroupValidationResult(
            group_name="g2",
            shape_type="arc",
            element_results=[
                ValidationResult(element_id="e3", shape_type="arc"),
            ],
        )
        report = AlignmentReport(
            file_path=Path("test.svg"),
            group_results=[group1, group2],
        )
        assert report.total_elements == 3


class TestParseRuleFile:
    """Tests for parse_rule_file function."""

    @pytest.fixture
    def valid_rule_file(self, tmp_path) -> Path:
        """Create a valid rule file."""
        content = """
groups:
  - name: "s-rect"
    shape: rect
    grid:
      x: 1.27
      y: 1.27
    size:
      width: 1.27
      height: 1.27

  - name: "s-circle"
    shape: arc
    grid:
      x: 1.27
      y: 1.27
    size:
      width: 0.635
      height: 0.635
    arc:
      start: 0
      end: 6.2831853

tolerance:
  acceptable: 0.001
  error_threshold: 0.1
"""
        rule_file = tmp_path / "rule.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_valid_rule(self, valid_rule_file):
        rule = parse_rule_file(valid_rule_file)

        assert len(rule.groups) == 2
        assert rule.tolerance.acceptable == 0.001
        assert rule.tolerance.error_threshold == 0.1

        # Check first group
        g1 = rule.groups[0]
        assert g1.name == "s-rect"
        assert g1.shape == "rect"
        assert g1.grid.x == 1.27
        assert g1.grid.y == 1.27
        assert g1.size.width == 1.27
        assert g1.size.height == 1.27
        assert g1.arc is None

        # Check second group
        g2 = rule.groups[1]
        assert g2.name == "s-circle"
        assert g2.shape == "arc"
        assert g2.arc is not None
        assert g2.arc.start == 0
        assert g2.arc.end == pytest.approx(6.2831853)

    @pytest.fixture
    def minimal_rule_file(self, tmp_path) -> Path:
        """Create a minimal rule file."""
        content = """
groups:
  - name: "shapes"
    shape: rect
"""
        rule_file = tmp_path / "minimal.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_minimal_rule(self, minimal_rule_file):
        rule = parse_rule_file(minimal_rule_file)

        assert len(rule.groups) == 1
        assert rule.groups[0].name == "shapes"
        assert rule.groups[0].grid is None
        assert rule.groups[0].size is None
        assert rule.tolerance.acceptable == DEFAULT_TOLERANCE
        assert rule.tolerance.error_threshold == DEFAULT_ERROR_THRESHOLD

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_rule_file(Path("/nonexistent/rule.yaml"))

    @pytest.fixture
    def invalid_rule_file(self, tmp_path) -> Path:
        """Create an invalid rule file."""
        content = """
groups:
  - name: "shapes"
"""
        rule_file = tmp_path / "invalid.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_rule(self, invalid_rule_file):
        with pytest.raises(ValueError, match="must have 'name' and 'shape'"):
            parse_rule_file(invalid_rule_file)


class TestFindGroupByLabel:
    """Tests for find_group_by_label function."""

    def test_find_existing_group(self):
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(f"{{{svg_ns}}}svg")
        group = ET.SubElement(
            root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "shapes"}
        )

        found = find_group_by_label(root, "shapes")
        assert found is group

    def test_find_nested_group(self):
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(f"{{{svg_ns}}}svg")
        layer = ET.SubElement(
            root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "Layer 1"}
        )
        shapes = ET.SubElement(
            layer, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "shapes"}
        )

        found = find_group_by_label(root, "shapes")
        assert found is shapes

    def test_group_not_found(self):
        svg_ns = SVG_NAMESPACES["svg"]
        root = ET.Element(f"{{{svg_ns}}}svg")

        found = find_group_by_label(root, "nonexistent")
        assert found is None


class TestIterShapesInGroup:
    """Tests for iter_shapes_in_group function."""

    def test_iter_rects(self):
        svg_ns = SVG_NAMESPACES["svg"]
        group = ET.Element(f"{{{svg_ns}}}g")
        ET.SubElement(
            group,
            f"{{{svg_ns}}}rect",
            {"id": "rect1", "x": "0", "y": "0", "width": "10", "height": "10"},
        )
        ET.SubElement(
            group,
            f"{{{svg_ns}}}rect",
            {"id": "rect2", "x": "20", "y": "20", "width": "10", "height": "10"},
        )
        ET.SubElement(group, f"{{{svg_ns}}}circle")  # Should be ignored

        shapes = list(iter_shapes_in_group(group, "rect"))
        assert len(shapes) == 2
        assert all(isinstance(s, RectInfo) for s in shapes)
        assert shapes[0].id == "rect1"
        assert shapes[1].id == "rect2"

    def test_iter_arcs(self):
        svg_ns = SVG_NAMESPACES["svg"]
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]

        group = ET.Element(f"{{{svg_ns}}}g")
        ET.SubElement(
            group,
            f"{{{svg_ns}}}path",
            {
                "id": "arc1",
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}cx": "50",
                f"{{{sodipodi_ns}}}cy": "50",
            },
        )
        ET.SubElement(
            group,
            f"{{{svg_ns}}}path",
            {"id": "path1", "d": "M0,0 L10,10"},  # Not an arc
        )

        shapes = list(iter_shapes_in_group(group, "arc"))
        assert len(shapes) == 1
        assert isinstance(shapes[0], ArcInfo)
        assert shapes[0].id == "arc1"


class TestValidateRect:
    """Tests for validate_rect function."""

    def test_valid_rect(self):
        elem = ET.Element("rect")
        info = RectInfo(element=elem, id="rect1", x=3.175, y=3.175, width=1.27, height=1.27)
        rule = GroupRule(
            name="test",
            shape="rect",
            grid=GridRule(x=1.27, y=1.27),
            size=SizeRule(width=1.27, height=1.27),
        )
        tolerance = ToleranceConfig()

        result = validate_rect(info, rule, tolerance)
        # Center is (3.175 + 0.635, 3.175 + 0.635) = (3.81, 3.81) = 3 * 1.27
        assert result.is_ok is True

    def test_invalid_size(self):
        elem = ET.Element("rect")
        # 1.3 is about 2.4% off from 1.27, which is within 10% threshold
        info = RectInfo(element=elem, id="rect1", x=0, y=0, width=1.3, height=1.3)
        rule = GroupRule(
            name="test",
            shape="rect",
            size=SizeRule(width=1.27, height=1.27),
        )
        tolerance = ToleranceConfig()

        result = validate_rect(info, rule, tolerance)
        assert result.has_fixable is True
        assert any(i.field == "width" for i in result.issues)
        assert any(i.field == "height" for i in result.issues)

    def test_invalid_position(self):
        elem = ET.Element("rect")
        # Center will be (5.1, 5.1), closest grid is 5.08
        # Deviation is 0.02, ratio = 0.02/1.27 ≈ 1.6%, within 10%
        info = RectInfo(element=elem, id="rect1", x=4.465, y=4.465, width=1.27, height=1.27)
        rule = GroupRule(
            name="test",
            shape="rect",
            grid=GridRule(x=1.27, y=1.27),
        )
        tolerance = ToleranceConfig()

        result = validate_rect(info, rule, tolerance)
        assert result.has_fixable is True


class TestValidateArc:
    """Tests for validate_arc function."""

    def test_valid_arc(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem,
            id="arc1",
            cx=5.08,
            cy=5.08,
            rx=0.3175,
            ry=0.3175,
            start=0,
            end=6.2831853,
        )
        rule = GroupRule(
            name="test",
            shape="arc",
            grid=GridRule(x=1.27, y=1.27),
            size=SizeRule(width=0.635, height=0.635),
            arc=ArcRule(start=0, end=6.2831853),
        )
        tolerance = ToleranceConfig()

        result = validate_arc(info, rule, tolerance)
        assert result.is_ok is True

    def test_invalid_end_angle(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem,
            id="arc1",
            cx=5.08,
            cy=5.08,
            rx=0.3175,
            ry=0.3175,
            start=0,
            end=6.217,  # Inkscape default incomplete circle
        )
        rule = GroupRule(
            name="test",
            shape="arc",
            arc=ArcRule(start=0, end=6.2831853),
        )
        tolerance = ToleranceConfig()

        result = validate_arc(info, rule, tolerance)
        assert result.has_fixable is True
        assert any(i.field == "end" for i in result.issues)


class TestFixRect:
    """Tests for fix_rect function."""

    def test_fix_size(self):
        elem = ET.Element("rect", {"x": "0", "y": "0", "width": "1.5", "height": "1.5"})
        info = RectInfo(element=elem, id="rect1", x=0, y=0, width=1.5, height=1.5)
        result = ValidationResult(
            element_id="rect1",
            shape_type="rect",
            issues=[
                Issue("rect1", "width", "fixable", 1.5, 1.27, 0.23, "msg"),
                Issue("rect1", "height", "fixable", 1.5, 1.27, 0.23, "msg"),
            ],
        )
        rule = GroupRule(name="test", shape="rect", size=SizeRule(width=1.27, height=1.27))

        fix_rect(info, result, rule)

        assert elem.get("width") == "1.27"
        assert elem.get("height") == "1.27"

    def test_fix_position(self):
        # Center is (0.5, 0.5), needs to snap to (0, 0) or (1.27, 1.27)
        elem = ET.Element("rect", {"x": "0", "y": "0", "width": "1", "height": "1"})
        info = RectInfo(element=elem, id="rect1", x=0, y=0, width=1, height=1)
        result = ValidationResult(
            element_id="rect1",
            shape_type="rect",
            issues=[
                Issue("rect1", "center_x", "fixable", 0.5, 0, 0.5, "msg"),
                Issue("rect1", "center_y", "fixable", 0.5, 0, 0.5, "msg"),
            ],
        )
        rule = GroupRule(name="test", shape="rect", grid=GridRule(x=1.27, y=1.27))

        fix_rect(info, result, rule)

        # New center should be 0, so new x = 0 - 1/2 = -0.5
        assert float(elem.get("x")) == pytest.approx(-0.5)
        assert float(elem.get("y")) == pytest.approx(-0.5)


class TestFixArc:
    """Tests for fix_arc function."""

    def test_fix_end_angle(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}cx": "5.08",
                f"{{{sodipodi_ns}}}cy": "5.08",
                f"{{{sodipodi_ns}}}start": "0",
                f"{{{sodipodi_ns}}}end": "6.217",
            },
        )
        info = ArcInfo(
            element=elem, id="arc1", cx=5.08, cy=5.08, rx=0.3175, ry=0.3175, start=0, end=6.217
        )
        result = ValidationResult(
            element_id="arc1",
            shape_type="arc",
            issues=[
                Issue("arc1", "end", "fixable", 6.217, 6.2831853, 0.066, "msg"),
            ],
        )
        rule = GroupRule(name="test", shape="arc", arc=ArcRule(start=0, end=6.2831853))

        fix_arc(info, result, rule)

        assert elem.get(f"{{{sodipodi_ns}}}end") == "6.2831853"


class TestValidateSvg:
    """Tests for validate_svg function."""

    @pytest.fixture
    def sample_svg(self, tmp_path) -> Path:
        """Create a sample SVG file."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     width="100" height="100">
  <g inkscape:label="s-rect">
    <rect id="rect1" x="3.175" y="3.175" width="1.27" height="1.27"/>
    <rect id="rect2" x="4.445" y="3.175" width="1.27" height="1.27"/>
  </g>
  <g inkscape:label="s-circle">
    <path id="arc1" sodipodi:type="arc"
          sodipodi:cx="5.08" sodipodi:cy="5.08"
          sodipodi:rx="0.3175" sodipodi:ry="0.3175"
          sodipodi:start="0" sodipodi:end="6.2831853"/>
  </g>
</svg>"""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(svg_content)
        return svg_file

    @pytest.fixture
    def rule(self) -> AlignmentRule:
        """Create a test rule."""
        return AlignmentRule(
            groups=[
                GroupRule(
                    name="s-rect",
                    shape="rect",
                    grid=GridRule(x=1.27, y=1.27),
                    size=SizeRule(width=1.27, height=1.27),
                ),
                GroupRule(
                    name="s-circle",
                    shape="arc",
                    grid=GridRule(x=1.27, y=1.27),
                    size=SizeRule(width=0.635, height=0.635),
                    arc=ArcRule(start=0, end=6.2831853),
                ),
            ],
            tolerance=ToleranceConfig(),
        )

    def test_validate_svg(self, sample_svg, rule):
        tree, report = validate_svg(sample_svg, rule, fix=False)

        assert report.file_path == sample_svg
        assert len(report.group_results) == 2
        assert report.total_elements == 3


class TestFormatReport:
    """Tests for format_report function."""

    def test_format_empty_report(self):
        report = AlignmentReport(file_path=Path("test.svg"))
        text = format_report(report)

        assert "test.svg" in text
        assert "Total elements checked: 0" in text

    def test_format_report_with_errors(self):
        error_result = ValidationResult(
            element_id="rect1",
            shape_type="rect",
            issues=[
                Issue("rect1", "width", "error", 5.0, 1.27, 3.73, "width=5.0")
            ],
        )
        group = GroupValidationResult(
            group_name="test",
            shape_type="rect",
            element_results=[error_result],
        )
        report = AlignmentReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_report(report)

        assert "ERROR" in text
        assert "rect1" in text
        assert "Output file will not be generated" in text

    def test_format_report_with_fixable(self):
        fixable_result = ValidationResult(
            element_id="rect1",
            shape_type="rect",
            issues=[
                Issue("rect1", "width", "fixable", 1.28, 1.27, 0.01, "width=1.28")
            ],
        )
        group = GroupValidationResult(
            group_name="test",
            shape_type="rect",
            element_results=[fixable_result],
        )
        report = AlignmentReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_report(report)

        assert "FIXABLE" in text
        assert "All fixable issues can be corrected" in text
