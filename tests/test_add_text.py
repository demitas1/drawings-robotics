"""Tests for svg_tools.add_text module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES
from svg_tools.add_text import (
    FontConfig,
    TextFormatConfig,
    TextLineRule,
    AddTextRule,
    TextElementInfo,
    GroupAddResult,
    AddTextReport,
    calculate_text_offset,
    px_to_mm,
    mm_to_px,
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
        assert config.size == 1.41111
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

    def test_basic_rule(self):
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
        # Check defaults
        assert rule.font.family == "Noto Sans CJK JP"
        assert rule.format.type == "number"

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


class TestGroupAddResult:
    """Tests for GroupAddResult dataclass."""

    def test_empty_result(self):
        result = GroupAddResult(
            group_name="test",
            y=2.54,
            x_start=5.08,
            x_end=10.16,
            x_interval=2.54,
        )
        assert result.element_count == 0
        assert result.has_errors is False

    def test_result_with_elements(self):
        result = GroupAddResult(
            group_name="test",
            y=2.54,
            x_start=5.08,
            x_end=10.16,
            x_interval=2.54,
            elements=[
                TextElementInfo("t1", "1", 5.08, 2.54, 5.0, 2.6),
                TextElementInfo("t2", "2", 7.62, 2.54, 7.5, 2.6),
            ],
        )
        assert result.element_count == 2

    def test_result_with_errors(self):
        result = GroupAddResult(
            group_name="test",
            y=2.54,
            x_start=5.08,
            x_end=10.16,
            x_interval=2.54,
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
            y=2.54,
            x_start=5.08,
            x_end=10.16,
            x_interval=2.54,
            elements=[
                TextElementInfo("t1", "1", 5.08, 2.54, 5.0, 2.6),
                TextElementInfo("t2", "2", 7.62, 2.54, 7.5, 2.6),
            ],
        )
        group2 = GroupAddResult(
            group_name="g2",
            y=5.08,
            x_start=5.08,
            x_end=7.62,
            x_interval=2.54,
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
            y=2.54,
            x_start=5.08,
            x_end=10.16,
            x_interval=2.54,
            errors=["Error"],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )
        assert report.has_errors is True


class TestCalculateTextOffset:
    """Tests for calculate_text_offset function."""

    def test_single_digit(self):
        offset_x, offset_y = calculate_text_offset(10.0, "1")
        # Width estimate: 1 * 10 * 0.55 = 5.5
        # Cap height estimate: 10 * 0.72 = 7.2
        # offset_x = -5.5/2 = -2.75
        # offset_y = 7.2/2 = 3.6
        assert offset_x == pytest.approx(-2.75)
        assert offset_y == pytest.approx(3.6)

    def test_double_digit(self):
        offset_x, offset_y = calculate_text_offset(10.0, "12")
        # Width estimate: 2 * 10 * 0.55 = 11.0
        # offset_x = -11.0/2 = -5.5
        assert offset_x == pytest.approx(-5.5)
        assert offset_y == pytest.approx(3.6)

    def test_triple_digit(self):
        offset_x, offset_y = calculate_text_offset(10.0, "123")
        # Width estimate: 3 * 10 * 0.55 = 16.5
        # offset_x = -16.5/2 = -8.25
        assert offset_x == pytest.approx(-8.25)
        assert offset_y == pytest.approx(3.6)

    def test_custom_ratios(self):
        offset_x, offset_y = calculate_text_offset(
            10.0, "1", cap_height_ratio=0.8, char_width_ratio=0.6
        )
        # Width: 1 * 10 * 0.6 = 6.0
        # Cap height: 10 * 0.8 = 8.0
        assert offset_x == pytest.approx(-3.0)
        assert offset_y == pytest.approx(4.0)


class TestConversionFunctions:
    """Tests for px_to_mm and mm_to_px."""

    def test_px_to_mm(self):
        # At 96 DPI: 1 inch = 96px = 25.4mm
        assert px_to_mm(96.0) == pytest.approx(25.4)
        assert px_to_mm(1.0) == pytest.approx(25.4 / 96.0)

    def test_mm_to_px(self):
        # At 96 DPI: 25.4mm = 1 inch = 96px
        assert mm_to_px(25.4) == pytest.approx(96.0)
        assert mm_to_px(1.0) == pytest.approx(96.0 / 25.4)

    def test_roundtrip(self):
        original = 10.0
        assert px_to_mm(mm_to_px(original)) == pytest.approx(original)
        assert mm_to_px(px_to_mm(original)) == pytest.approx(original)


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

        # Check style
        style = elem.get("style")
        assert "font-family:Arial" in style
        assert "font-size:10.0px" in style
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
        assert g.font.size == 1.41111
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
    def missing_required_file(self, tmp_path) -> Path:
        """Create a rule file missing required fields."""
        content = """
groups:
  - name: "labels"
    y: 2.54
"""
        rule_file = tmp_path / "missing.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_missing_required_fields(self, missing_required_file):
        with pytest.raises(ValueError, match="must have"):
            parse_add_text_rule_file(missing_required_file)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_add_text_rule_file(Path("/nonexistent/rule.yaml"))


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

    def test_format_report_with_elements(self):
        group = GroupAddResult(
            group_name="labels",
            y=2.54,
            x_start=0.0,
            x_end=5.08,
            x_interval=2.54,
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
        assert "Y: 2.54 mm" in text
        assert "Elements: 3" in text
        assert "Total elements: 3" in text

    def test_format_report_with_errors(self):
        group = GroupAddResult(
            group_name="labels",
            y=2.54,
            x_start=0.0,
            x_end=5.08,
            x_interval=2.54,
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
            y=2.54,
            x_start=0.0,
            x_end=5.08,
            x_interval=2.54,
            warnings=["Some warning"],
        )
        report = AddTextReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_add_text_report(report)

        assert "[WARNING]" in text
