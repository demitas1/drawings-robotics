"""Tests for svg_tools.add_text module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES
from svg_tools.add_text import (
    AlignType,
    FontConfig,
    TextFormatConfig,
    TextLineRule,
    AddTextRule,
    TextElementInfo,
    GroupAddResult,
    AddTextReport,
    calculate_text_offset_estimated,
    calculate_text_offset_freetype,
    create_text_element,
    generate_grid_positions,
    generate_text_label,
    create_text_group,
    parse_add_text_rule_file,
    add_text_to_svg,
    format_add_text_report,
)


class TestFontConfig:
    """Tests for FontConfig dataclass."""

    def test_default_values(self):
        config = FontConfig()
        assert config.family == "Noto Sans CJK JP"
        assert config.size == 1.0  # mm
        assert config.color == "#000000"

    def test_custom_values(self):
        config = FontConfig(family="Arial", size=12.0, color="#ff0000")
        assert config.family == "Arial"
        assert config.size == 12.0
        assert config.color == "#ff0000"


class TestTextFormatConfig:
    """Tests for TextFormatConfig dataclass."""

    def test_default_values(self):
        config = TextFormatConfig()
        assert config.type == "number"
        assert config.padding == 0
        assert config.start == 1
        assert config.custom == []

    def test_custom_values(self):
        config = TextFormatConfig(
            type="letter",
            padding=2,
            start=0,
            custom=["x", "y", "z"],
        )
        assert config.type == "letter"
        assert config.padding == 2
        assert config.start == 0
        assert config.custom == ["x", "y", "z"]


class TestTextLineRule:
    """Tests for TextLineRule dataclass."""

    def test_horizontal_rule(self):
        """Test horizontal layout (y fixed, x varies)."""
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=5.08,
            x_end=20.32,
            x_interval=2.54,
        )
        assert rule.name == "labels"
        assert rule.y == 2.54
        assert rule.x_start == 5.08
        assert rule.x_end == 20.32
        assert rule.x_interval == 2.54
        # Check layout properties
        assert rule.is_horizontal is True
        assert rule.is_vertical is False
        assert rule.fixed_coord == 2.54
        assert rule.start_coord == 5.08
        assert rule.end_coord == 20.32
        assert rule.interval == 2.54
        # Check defaults
        assert rule.font.family == "Noto Sans CJK JP"
        assert rule.format.type == "number"

    def test_vertical_rule(self):
        """Test vertical layout (x fixed, y varies)."""
        rule = TextLineRule(
            name="row-labels",
            x=2.54,
            y_start=5.08,
            y_end=38.1,
            y_interval=2.54,
        )
        assert rule.name == "row-labels"
        assert rule.x == 2.54
        assert rule.y_start == 5.08
        assert rule.y_end == 38.1
        assert rule.y_interval == 2.54
        # Check layout properties
        assert rule.is_horizontal is False
        assert rule.is_vertical is True
        assert rule.fixed_coord == 2.54
        assert rule.start_coord == 5.08
        assert rule.end_coord == 38.1
        assert rule.interval == 2.54

    def test_rule_with_font_and_format(self):
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=5.08,
            x_end=20.32,
            x_interval=2.54,
            font=FontConfig(family="Arial", size=10.0, color="#0000ff"),
            format=TextFormatConfig(type="letter_upper", start=1),
        )
        assert rule.font.family == "Arial"
        assert rule.font.size == 10.0
        assert rule.format.type == "letter_upper"

    def test_default_align(self):
        """Test default align is bbox_center."""
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=5.08,
            x_end=20.32,
            x_interval=2.54,
        )
        assert rule.align == "bbox_center"

    def test_custom_align(self):
        """Test custom align value."""
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=5.08,
            x_end=20.32,
            x_interval=2.54,
            align="baseline_center",
        )
        assert rule.align == "baseline_center"


class TestGroupAddResult:
    """Tests for GroupAddResult dataclass."""

    def test_empty_horizontal_result(self):
        """Test empty horizontal layout result."""
        result = GroupAddResult(
            group_name="test",
            fixed_axis="y",
            fixed_value=2.54,
            start=5.08,
            end=10.16,
            interval=2.54,
        )
        assert result.element_count == 0
        assert result.has_errors is False
        assert result.is_vertical is False

    def test_empty_vertical_result(self):
        """Test empty vertical layout result."""
        result = GroupAddResult(
            group_name="test",
            fixed_axis="x",
            fixed_value=2.54,
            start=5.08,
            end=38.1,
            interval=2.54,
        )
        assert result.element_count == 0
        assert result.has_errors is False
        assert result.is_vertical is True

    def test_result_with_elements(self):
        result = GroupAddResult(
            group_name="test",
            fixed_axis="y",
            fixed_value=2.54,
            start=5.08,
            end=10.16,
            interval=2.54,
            elements=[
                TextElementInfo("t1", "1", 5.08, 2.54, 5.0, 2.6),
                TextElementInfo("t2", "2", 7.62, 2.54, 7.5, 2.6),
            ],
        )
        assert result.element_count == 2

    def test_result_with_errors(self):
        result = GroupAddResult(
            group_name="test",
            fixed_axis="y",
            fixed_value=2.54,
            start=5.08,
            end=10.16,
            interval=2.54,
            errors=["Some error"],
        )
        assert result.has_errors is True


class TestAddTextReport:
    """Tests for AddTextReport dataclass."""

    def test_empty_report(self):
        report = AddTextReport(file_path=Path("test.svg"))
        assert report.has_errors is False
        assert report.total_elements == 0

    def test_report_with_groups(self):
        group1 = GroupAddResult(
            group_name="g1",
            fixed_axis="y",
            fixed_value=2.54,
            start=5.08,
            end=10.16,
            interval=2.54,
            elements=[
                TextElementInfo("t1", "1", 5.08, 2.54, 5.0, 2.6),
                TextElementInfo("t2", "2", 7.62, 2.54, 7.5, 2.6),
            ],
        )
        group2 = GroupAddResult(
            group_name="g2",
            fixed_axis="y",
            fixed_value=5.08,
            start=5.08,
            end=7.62,
            interval=2.54,
            elements=[
                TextElementInfo("t3", "A", 5.08, 5.08, 5.0, 5.1),
            ],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group1, group2],
        )
        assert report.total_elements == 3
        assert report.has_errors is False

    def test_report_with_errors(self):
        group = GroupAddResult(
            group_name="g1",
            fixed_axis="y",
            fixed_value=2.54,
            start=5.08,
            end=10.16,
            interval=2.54,
            errors=["Error"],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )
        assert report.has_errors is True


class TestCalculateTextOffset:
    """Tests for calculate_text_offset_estimated function."""

    def test_single_digit(self):
        # Using default ratios: cap_height_ratio=0.75, char_width_ratio=0.50
        offset_x, offset_y = calculate_text_offset_estimated(10.0, "1")
        # Width estimate: 1 * 10 * 0.50 = 5.0
        # Cap height estimate: 10 * 0.75 = 7.5
        # offset_x = -5.0/2 = -2.5
        # offset_y = 7.5/2 = 3.75
        assert offset_x == pytest.approx(-2.5)
        assert offset_y == pytest.approx(3.75)

    def test_double_digit(self):
        offset_x, offset_y = calculate_text_offset_estimated(10.0, "12")
        # Width estimate: 2 * 10 * 0.50 = 10.0
        # offset_x = -10.0/2 = -5.0
        assert offset_x == pytest.approx(-5.0)
        assert offset_y == pytest.approx(3.75)

    def test_triple_digit(self):
        offset_x, offset_y = calculate_text_offset_estimated(10.0, "123")
        # Width estimate: 3 * 10 * 0.50 = 15.0
        # offset_x = -15.0/2 = -7.5
        assert offset_x == pytest.approx(-7.5)
        assert offset_y == pytest.approx(3.75)

    def test_custom_ratios(self):
        offset_x, offset_y = calculate_text_offset_estimated(
            10.0, "1", cap_height_ratio=0.8, char_width_ratio=0.6
        )
        # Width: 1 * 10 * 0.6 = 6.0
        # Cap height: 10 * 0.8 = 8.0
        assert offset_x == pytest.approx(-3.0)
        assert offset_y == pytest.approx(4.0)

    def test_baseline_center_align(self):
        """Test baseline_center alignment mode."""
        offset_x, offset_y = calculate_text_offset_estimated(
            10.0, "1", align="baseline_center"
        )
        # Width estimate: 1 * 10 * 0.50 = 5.0
        # offset_x = -5.0/2 = -2.5
        # offset_y = 0 (baseline at grid Y)
        assert offset_x == pytest.approx(-2.5)
        assert offset_y == pytest.approx(0)

    def test_bbox_center_align_explicit(self):
        """Test explicit bbox_center alignment mode."""
        offset_x, offset_y = calculate_text_offset_estimated(
            10.0, "1", align="bbox_center"
        )
        # Same as default behavior
        assert offset_x == pytest.approx(-2.5)
        assert offset_y == pytest.approx(3.75)


class TestGenerateGridPositions:
    """Tests for generate_grid_positions function."""

    def test_single_position(self):
        positions = generate_grid_positions(5.08, 5.08, 2.54)
        assert positions == [5.08]

    def test_multiple_positions(self):
        positions = generate_grid_positions(0.0, 7.62, 2.54)
        assert len(positions) == 4
        assert positions[0] == pytest.approx(0.0)
        assert positions[1] == pytest.approx(2.54)
        assert positions[2] == pytest.approx(5.08)
        assert positions[3] == pytest.approx(7.62)

    def test_non_aligned_end(self):
        # End position not exactly on grid
        positions = generate_grid_positions(0.0, 6.0, 2.54)
        # Should include 0, 2.54, 5.08 (not 7.62 because > 6.0)
        assert len(positions) == 3
        assert positions[0] == pytest.approx(0.0)
        assert positions[1] == pytest.approx(2.54)
        assert positions[2] == pytest.approx(5.08)

    def test_zero_interval(self):
        # Zero interval should return just start
        positions = generate_grid_positions(5.08, 10.16, 0.0)
        assert positions == [5.08]

    def test_negative_interval(self):
        # Negative interval should return just start
        positions = generate_grid_positions(5.08, 10.16, -2.54)
        assert positions == [5.08]


class TestGenerateTextLabel:
    """Tests for generate_text_label function."""

    def test_number_format(self):
        fmt = TextFormatConfig(type="number", start=1)
        assert generate_text_label(1, fmt) == "1"
        assert generate_text_label(10, fmt) == "10"

    def test_number_with_padding(self):
        fmt = TextFormatConfig(type="number", padding=2, start=1)
        assert generate_text_label(1, fmt) == "01"
        assert generate_text_label(10, fmt) == "10"
        assert generate_text_label(100, fmt) == "100"

    def test_letter_format(self):
        fmt = TextFormatConfig(type="letter", start=1)
        assert generate_text_label(1, fmt) == "a"
        assert generate_text_label(26, fmt) == "z"
        assert generate_text_label(27, fmt) == "aa"

    def test_letter_upper_format(self):
        fmt = TextFormatConfig(type="letter_upper", start=1)
        assert generate_text_label(1, fmt) == "A"
        assert generate_text_label(26, fmt) == "Z"

    def test_custom_format(self):
        fmt = TextFormatConfig(type="custom", custom=["α", "β", "γ"])
        assert generate_text_label(1, fmt) == "α"
        assert generate_text_label(2, fmt) == "β"
        assert generate_text_label(3, fmt) == "γ"

    def test_custom_format_out_of_range(self):
        fmt = TextFormatConfig(type="custom", custom=["a", "b"])
        with pytest.raises(ValueError):
            generate_text_label(3, fmt)


class TestCreateTextElement:
    """Tests for create_text_element function."""

    def test_basic_element(self):
        font = FontConfig(family="Arial", size=10.0, color="#000000")
        elem, info = create_text_element(5.08, 2.54, "1", font, "text-1")

        # Check element attributes
        svg_ns = SVG_NAMESPACES["svg"]
        assert elem.tag == f"{{{svg_ns}}}text"
        assert elem.get("id") == "text-1"
        assert elem.text == "1"

        # Check style (font-size is unitless for SVG viewBox compatibility)
        style = elem.get("style")
        assert "font-family:Arial" in style
        assert "font-size:10.0" in style  # unitless (viewBox units = mm)
        assert "fill:#000000" in style

        # Check info
        assert info.element_id == "text-1"
        assert info.text == "1"
        assert info.grid_x == 5.08
        assert info.grid_y == 2.54

    def test_element_position_offset(self):
        font = FontConfig(size=10.0)
        elem, info = create_text_element(0.0, 0.0, "1", font, "text-1")

        # At grid (0,0), text should be offset for centering
        x = float(elem.get("x"))
        y = float(elem.get("y"))

        # x should be negative (shifted left from center)
        assert x < 0

        # y should be positive (shifted down from center for baseline)
        assert y > 0

    def test_element_baseline_center_align(self):
        """Test element creation with baseline_center alignment."""
        font = FontConfig(size=10.0)
        elem, info = create_text_element(
            5.0, 10.0, "1", font, "text-1", align="baseline_center"
        )

        # At grid (5.0, 10.0), text should be horizontally centered
        x = float(elem.get("x"))
        y = float(elem.get("y"))

        # x should be shifted left from grid center
        assert x < 5.0

        # y should be exactly at grid Y (baseline at grid Y)
        assert y == pytest.approx(10.0)


class TestCreateTextGroup:
    """Tests for create_text_group function."""

    def test_basic_group(self):
        rule = TextLineRule(
            name="col-labels",
            y=2.54,
            x_start=0.0,
            x_end=5.08,
            x_interval=2.54,
            format=TextFormatConfig(type="number", start=1),
        )
        group, result = create_text_group(rule)

        # Check group attributes
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        assert group.tag == f"{{{svg_ns}}}g"
        assert group.get("id") == "col-labels"
        assert group.get(f"{{{inkscape_ns}}}label") == "col-labels"

        # Check children
        children = list(group)
        assert len(children) == 3

        # Check result
        assert result.group_name == "col-labels"
        assert result.element_count == 3
        assert not result.has_errors

        # Check element labels
        labels = [info.text for info in result.elements]
        assert labels == ["1", "2", "3"]

    def test_letter_format(self):
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=0.0,
            x_end=5.08,
            x_interval=2.54,
            format=TextFormatConfig(type="letter", start=1),
        )
        group, result = create_text_group(rule)

        labels = [info.text for info in result.elements]
        assert labels == ["a", "b", "c"]

    def test_custom_id_prefix(self):
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=0.0,
            x_end=2.54,
            x_interval=2.54,
        )
        group, result = create_text_group(rule, id_prefix="custom-id")

        ids = [info.element_id for info in result.elements]
        assert ids == ["custom-id-1", "custom-id-2"]

    def test_single_element(self):
        rule = TextLineRule(
            name="single",
            y=2.54,
            x_start=5.08,
            x_end=5.08,
            x_interval=2.54,
        )
        group, result = create_text_group(rule)

        assert result.element_count == 1

    def test_custom_format_error(self):
        # Custom format with insufficient labels
        rule = TextLineRule(
            name="labels",
            y=2.54,
            x_start=0.0,
            x_end=7.62,  # Would need 4 labels
            x_interval=2.54,
            format=TextFormatConfig(type="custom", custom=["a", "b"]),  # Only 2 labels
        )
        group, result = create_text_group(rule)

        # First two should succeed, rest should error
        assert len(result.elements) == 2
        assert len(result.errors) == 2

    def test_vertical_group(self):
        """Test vertical layout (x fixed, y varies)."""
        rule = TextLineRule(
            name="row-labels",
            x=2.54,
            y_start=0.0,
            y_end=5.08,
            y_interval=2.54,
            format=TextFormatConfig(type="letter", start=1),
        )
        group, result = create_text_group(rule)

        # Check group attributes
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        assert group.tag == f"{{{svg_ns}}}g"
        assert group.get("id") == "row-labels"
        assert group.get(f"{{{inkscape_ns}}}label") == "row-labels"

        # Check children
        children = list(group)
        assert len(children) == 3

        # Check result
        assert result.group_name == "row-labels"
        assert result.is_vertical is True
        assert result.fixed_value == 2.54
        assert result.element_count == 3
        assert not result.has_errors

        # Check element labels
        labels = [info.text for info in result.elements]
        assert labels == ["a", "b", "c"]

        # Check element positions (x fixed, y varies)
        for i, info in enumerate(result.elements):
            assert info.grid_x == pytest.approx(2.54)  # x is fixed
            expected_y = i * 2.54  # y varies: 0.0, 2.54, 5.08
            assert info.grid_y == pytest.approx(expected_y)

    def test_vertical_custom_labels_with_skip(self):
        """Test vertical layout with custom labels including skip marker."""
        rule = TextLineRule(
            name="row-labels",
            x=2.54,
            y_start=0.0,
            y_end=7.62,
            y_interval=2.54,
            format=TextFormatConfig(type="custom", custom=["a", "b", "_", "c"]),
        )
        group, result = create_text_group(rule)

        # "a", "b" succeed, "_" errors, "c" succeeds
        assert len(result.elements) == 3
        assert len(result.errors) == 1  # Skip marker error
        labels = [info.text for info in result.elements]
        assert labels == ["a", "b", "c"]


class TestParseAddTextRuleFile:
    """Tests for parse_add_text_rule_file function."""

    @pytest.fixture
    def valid_rule_file(self, tmp_path) -> Path:
        """Create a valid rule file."""
        content = """
groups:
  - name: "col-labels"
    y: 2.54
    x_start: 5.08
    x_end: 78.74
    x_interval: 2.54
    font:
      family: "Noto Sans CJK JP"
      size: 1.41111
      color: "#0000ff"
    format:
      type: number
      padding: 0
      start: 1

  - name: "row-labels"
    y: 5.08
    x_start: 2.54
    x_end: 2.54
    x_interval: 2.54
    format:
      type: letter
"""
        rule_file = tmp_path / "rule.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_valid_rule(self, valid_rule_file):
        rule = parse_add_text_rule_file(valid_rule_file)

        assert len(rule.groups) == 2

        # Check first group
        g1 = rule.groups[0]
        assert g1.name == "col-labels"
        assert g1.y == 2.54
        assert g1.x_start == 5.08
        assert g1.x_end == 78.74
        assert g1.x_interval == 2.54
        assert g1.font.family == "Noto Sans CJK JP"
        assert g1.font.color == "#0000ff"
        assert g1.format.type == "number"

        # Check second group
        g2 = rule.groups[1]
        assert g2.name == "row-labels"
        assert g2.format.type == "letter"

    @pytest.fixture
    def minimal_rule_file(self, tmp_path) -> Path:
        """Create a minimal rule file."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
    x_end: 10.16
    x_interval: 2.54
"""
        rule_file = tmp_path / "minimal.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_minimal_rule(self, minimal_rule_file):
        rule = parse_add_text_rule_file(minimal_rule_file)

        assert len(rule.groups) == 1
        g = rule.groups[0]
        # Check defaults
        assert g.font.family == "Noto Sans CJK JP"
        assert g.font.size == 1.0  # mm
        assert g.font.color == "#000000"
        assert g.format.type == "number"
        assert g.format.padding == 0
        assert g.format.start == 1

    @pytest.fixture
    def custom_format_rule_file(self, tmp_path) -> Path:
        """Create a rule file with custom format."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
    format:
      type: custom
      custom: [α, β, γ]
"""
        rule_file = tmp_path / "custom.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_custom_format(self, custom_format_rule_file):
        rule = parse_add_text_rule_file(custom_format_rule_file)

        g = rule.groups[0]
        assert g.format.type == "custom"
        assert g.format.custom == ["α", "β", "γ"]

    @pytest.fixture
    def missing_custom_labels_file(self, tmp_path) -> Path:
        """Create a rule file with custom type but no labels."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
    format:
      type: custom
"""
        rule_file = tmp_path / "missing_custom.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_missing_custom_labels(self, missing_custom_labels_file):
        with pytest.raises(ValueError, match="custom is required"):
            parse_add_text_rule_file(missing_custom_labels_file)

    @pytest.fixture
    def missing_horizontal_fields_file(self, tmp_path) -> Path:
        """Create a rule file with incomplete horizontal layout fields."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
"""
        rule_file = tmp_path / "missing_horizontal.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_missing_horizontal_fields(self, missing_horizontal_fields_file):
        """Test error when horizontal layout fields are incomplete."""
        with pytest.raises(ValueError, match="Horizontal layout requires"):
            parse_add_text_rule_file(missing_horizontal_fields_file)

    @pytest.fixture
    def missing_vertical_fields_file(self, tmp_path) -> Path:
        """Create a rule file with incomplete vertical layout fields."""
        content = """
groups:
  - name: "labels"
    x: 2.54
    y_start: 0.0
"""
        rule_file = tmp_path / "missing_vertical.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_missing_vertical_fields(self, missing_vertical_fields_file):
        """Test error when vertical layout fields are incomplete."""
        with pytest.raises(ValueError, match="Vertical layout requires"):
            parse_add_text_rule_file(missing_vertical_fields_file)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_add_text_rule_file(Path("/nonexistent/rule.yaml"))

    @pytest.fixture
    def vertical_rule_file(self, tmp_path) -> Path:
        """Create a vertical layout rule file."""
        content = """
groups:
  - name: "row-labels"
    x: 2.54
    y_start: 5.08
    y_end: 38.1
    y_interval: 2.54
    font:
      family: "Noto Sans CJK JP"
      size: 1.4
      color: "#0000ff"
    format:
      type: custom
      custom: [a, b, c, d, e, f, _, _, g, h, i, j, k, l]
"""
        rule_file = tmp_path / "vertical.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_vertical_rule(self, vertical_rule_file):
        """Test parsing vertical layout rule."""
        rule = parse_add_text_rule_file(vertical_rule_file)

        assert len(rule.groups) == 1
        g = rule.groups[0]
        assert g.name == "row-labels"
        assert g.x == 2.54
        assert g.y_start == 5.08
        assert g.y_end == 38.1
        assert g.y_interval == 2.54
        assert g.is_vertical is True
        assert g.is_horizontal is False
        assert g.format.type == "custom"
        assert len(g.format.custom) == 14

    @pytest.fixture
    def mixed_layout_rule_file(self, tmp_path) -> Path:
        """Create a rule file with both horizontal and vertical layouts."""
        content = """
groups:
  - name: "col-labels"
    y: 2.54
    x_start: 5.08
    x_end: 78.74
    x_interval: 2.54
    format:
      type: number

  - name: "row-labels"
    x: 2.54
    y_start: 5.08
    y_end: 15.24
    y_interval: 2.54
    format:
      type: letter
"""
        rule_file = tmp_path / "mixed.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_mixed_layout_rule(self, mixed_layout_rule_file):
        """Test parsing rule with both horizontal and vertical layouts."""
        rule = parse_add_text_rule_file(mixed_layout_rule_file)

        assert len(rule.groups) == 2

        g1 = rule.groups[0]
        assert g1.name == "col-labels"
        assert g1.is_horizontal is True
        assert g1.is_vertical is False

        g2 = rule.groups[1]
        assert g2.name == "row-labels"
        assert g2.is_horizontal is False
        assert g2.is_vertical is True

    @pytest.fixture
    def invalid_both_layouts_file(self, tmp_path) -> Path:
        """Create an invalid rule file with both layout types."""
        content = """
groups:
  - name: "invalid"
    y: 2.54
    x_start: 5.08
    x_end: 10.16
    x_interval: 2.54
    x: 2.54
    y_start: 5.08
    y_end: 10.16
    y_interval: 2.54
"""
        rule_file = tmp_path / "invalid_both.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_both_layouts(self, invalid_both_layouts_file):
        """Test error when both horizontal and vertical fields specified."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            parse_add_text_rule_file(invalid_both_layouts_file)

    @pytest.fixture
    def invalid_no_layout_file(self, tmp_path) -> Path:
        """Create an invalid rule file with neither layout type."""
        content = """
groups:
  - name: "invalid"
    format:
      type: number
"""
        rule_file = tmp_path / "invalid_no_layout.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_no_layout(self, invalid_no_layout_file):
        """Test error when neither horizontal nor vertical fields specified."""
        with pytest.raises(ValueError, match="Must specify either"):
            parse_add_text_rule_file(invalid_no_layout_file)

    @pytest.fixture
    def align_rule_file(self, tmp_path) -> Path:
        """Create a rule file with align field."""
        content = """
groups:
  - name: "bbox-labels"
    y: 2.54
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
    align: bbox_center

  - name: "baseline-labels"
    y: 5.08
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
    align: baseline_center
"""
        rule_file = tmp_path / "align.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_align_field(self, align_rule_file):
        """Test parsing align field."""
        rule = parse_add_text_rule_file(align_rule_file)

        assert len(rule.groups) == 2
        assert rule.groups[0].align == "bbox_center"
        assert rule.groups[1].align == "baseline_center"

    @pytest.fixture
    def default_align_rule_file(self, tmp_path) -> Path:
        """Create a rule file without align field (should use default)."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
"""
        rule_file = tmp_path / "default_align.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_default_align(self, default_align_rule_file):
        """Test default align value when not specified."""
        rule = parse_add_text_rule_file(default_align_rule_file)

        assert len(rule.groups) == 1
        assert rule.groups[0].align == "bbox_center"

    @pytest.fixture
    def invalid_align_rule_file(self, tmp_path) -> Path:
        """Create a rule file with invalid align value."""
        content = """
groups:
  - name: "labels"
    y: 2.54
    x_start: 0.0
    x_end: 5.08
    x_interval: 2.54
    align: invalid_value
"""
        rule_file = tmp_path / "invalid_align.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_align(self, invalid_align_rule_file):
        """Test error when invalid align value is specified."""
        with pytest.raises(ValueError, match="Invalid align value"):
            parse_add_text_rule_file(invalid_align_rule_file)


class TestAddTextToSvg:
    """Tests for add_text_to_svg function."""

    @pytest.fixture
    def sample_svg(self, tmp_path) -> Path:
        """Create a sample SVG file."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     width="100mm" height="100mm">
  <g inkscape:label="existing">
    <rect id="rect1" x="0" y="0" width="10" height="10"/>
  </g>
</svg>"""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(svg_content)
        return svg_file

    @pytest.fixture
    def rule(self) -> AddTextRule:
        """Create a test rule."""
        return AddTextRule(
            groups=[
                TextLineRule(
                    name="col-labels",
                    y=2.54,
                    x_start=0.0,
                    x_end=5.08,
                    x_interval=2.54,
                    format=TextFormatConfig(type="number", start=1),
                ),
            ],
        )

    def test_add_text_without_apply(self, sample_svg, rule):
        tree, report = add_text_to_svg(sample_svg, rule, apply=False)

        assert report.file_path == sample_svg
        assert len(report.group_results) == 1
        assert report.total_elements == 3
        assert not report.has_errors

        # Check that group was NOT added to tree
        root = tree.getroot()
        groups = list(root)
        assert len(groups) == 1  # Only existing group

    def test_add_text_with_apply(self, sample_svg, rule):
        tree, report = add_text_to_svg(sample_svg, rule, apply=True)

        assert not report.has_errors

        # Check that group was added to tree
        root = tree.getroot()
        groups = list(root)
        assert len(groups) == 2  # Existing + new

        # Find new group
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        new_group = None
        for g in groups:
            if g.get(f"{{{inkscape_ns}}}label") == "col-labels":
                new_group = g
                break

        assert new_group is not None
        assert len(list(new_group)) == 3  # 3 text elements

    def test_add_text_with_output(self, sample_svg, rule, tmp_path):
        tree, report = add_text_to_svg(sample_svg, rule, apply=True)

        # Write output
        output_file = tmp_path / "output.svg"
        tree.write(output_file, encoding="unicode", xml_declaration=True)

        # Verify output file
        assert output_file.exists()

        # Parse and verify
        output_tree = ET.parse(output_file)
        root = output_tree.getroot()
        groups = list(root)
        assert len(groups) == 2


class TestFormatAddTextReport:
    """Tests for format_add_text_report function."""

    def test_format_empty_report(self):
        report = AddTextReport(file_path=Path("test.svg"))
        text = format_add_text_report(report)

        assert "test.svg" in text
        assert "Total elements: 0" in text

    def test_format_horizontal_report_with_elements(self):
        """Test formatting horizontal layout report."""
        group = GroupAddResult(
            group_name="labels",
            fixed_axis="y",
            fixed_value=2.54,
            start=0.0,
            end=5.08,
            interval=2.54,
            elements=[
                TextElementInfo("t1", "1", 0.0, 2.54, -0.1, 2.6),
                TextElementInfo("t2", "2", 2.54, 2.54, 2.44, 2.6),
                TextElementInfo("t3", "3", 5.08, 2.54, 4.98, 2.6),
            ],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_add_text_report(report)

        assert "labels" in text
        assert "Layout: horizontal" in text
        assert "Y: 2.54 mm" in text
        assert "X range: 0.00 - 5.08 mm" in text
        assert "Elements: 3" in text
        assert "Total elements: 3" in text

    def test_format_vertical_report_with_elements(self):
        """Test formatting vertical layout report."""
        group = GroupAddResult(
            group_name="row-labels",
            fixed_axis="x",
            fixed_value=2.54,
            start=0.0,
            end=5.08,
            interval=2.54,
            elements=[
                TextElementInfo("t1", "a", 2.54, 0.0, 2.5, 0.1),
                TextElementInfo("t2", "b", 2.54, 2.54, 2.5, 2.64),
                TextElementInfo("t3", "c", 2.54, 5.08, 2.5, 5.18),
            ],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_add_text_report(report)

        assert "row-labels" in text
        assert "Layout: vertical" in text
        assert "X: 2.54 mm" in text
        assert "Y range: 0.00 - 5.08 mm" in text
        assert "Elements: 3" in text
        assert "Total elements: 3" in text

    def test_format_report_with_errors(self):
        group = GroupAddResult(
            group_name="labels",
            fixed_axis="y",
            fixed_value=2.54,
            start=0.0,
            end=5.08,
            interval=2.54,
            errors=["Failed to generate label"],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_add_text_report(report)

        assert "[ERROR]" in text
        assert "Output file will not be generated" in text

    def test_format_report_with_warnings(self):
        group = GroupAddResult(
            group_name="labels",
            fixed_axis="y",
            fixed_value=2.54,
            start=0.0,
            end=5.08,
            interval=2.54,
            warnings=["Some warning"],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_add_text_report(report)

        assert "[WARNING]" in text
