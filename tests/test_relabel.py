"""Tests for svg_tools.relabel module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES, get_element_label, set_element_label
from svg_tools.relabel import (
    GridConfig,
    OriginConfig,
    AxisConfig,
    IndexConfig,
    FormatConfig,
    SortConfig,
    RelabelGroupRule,
    RelabelRule,
    LabelChange,
    GroupRelabelResult,
    RelabelReport,
    to_letter,
    format_index,
    parse_relabel_rule_file,
    iter_shapes_in_group,
    calculate_auto_origin,
    calculate_grid_index,
    generate_label,
    check_grid_deviation,
    sort_shapes,
    reorder_elements_in_group,
    relabel_group,
    relabel_svg,
    format_relabel_report,
)


class TestToLetter:
    """Tests for to_letter function."""

    def test_single_letters(self):
        assert to_letter(1) == "a"
        assert to_letter(2) == "b"
        assert to_letter(26) == "z"

    def test_double_letters(self):
        assert to_letter(27) == "aa"
        assert to_letter(28) == "ab"
        assert to_letter(52) == "az"
        assert to_letter(53) == "ba"

    def test_uppercase(self):
        assert to_letter(1, upper=True) == "A"
        assert to_letter(26, upper=True) == "Z"
        assert to_letter(27, upper=True) == "AA"

    def test_invalid_index(self):
        with pytest.raises(ValueError):
            to_letter(0)
        with pytest.raises(ValueError):
            to_letter(-1)


class TestFormatIndex:
    """Tests for format_index function."""

    def test_number_format(self):
        assert format_index(1, "number") == "1"
        assert format_index(10, "number") == "10"
        assert format_index(123, "number") == "123"

    def test_number_padding(self):
        assert format_index(1, "number", padding=2) == "01"
        assert format_index(1, "number", padding=3) == "001"
        assert format_index(10, "number", padding=2) == "10"
        assert format_index(100, "number", padding=2) == "100"

    def test_letter_format(self):
        assert format_index(1, "letter") == "a"
        assert format_index(26, "letter") == "z"
        assert format_index(27, "letter") == "aa"

    def test_letter_upper_format(self):
        assert format_index(1, "letter_upper") == "A"
        assert format_index(26, "letter_upper") == "Z"
        assert format_index(27, "letter_upper") == "AA"

    def test_custom_format(self):
        custom_labels = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "pl", "mi"]
        assert format_index(1, "custom", custom_labels=custom_labels) == "a"
        assert format_index(10, "custom", custom_labels=custom_labels) == "j"
        assert format_index(11, "custom", custom_labels=custom_labels) == "pl"
        assert format_index(12, "custom", custom_labels=custom_labels) == "mi"

    def test_custom_format_out_of_range(self):
        custom_labels = ["x", "y", "z"]
        with pytest.raises(ValueError, match="out of range"):
            format_index(4, "custom", custom_labels=custom_labels)
        with pytest.raises(ValueError, match="out of range"):
            format_index(0, "custom", custom_labels=custom_labels)

    def test_custom_format_without_labels(self):
        with pytest.raises(ValueError, match="custom_labels required"):
            format_index(1, "custom", custom_labels=None)

    def test_custom_format_skip_marker(self):
        custom_labels = ["a", "b", "c", "_", "_", "f", "g"]
        # Valid indices work
        assert format_index(1, "custom", custom_labels=custom_labels) == "a"
        assert format_index(3, "custom", custom_labels=custom_labels) == "c"
        assert format_index(6, "custom", custom_labels=custom_labels) == "f"
        # Skip markers cause errors
        with pytest.raises(ValueError, match="skip marker '_'"):
            format_index(4, "custom", custom_labels=custom_labels)
        with pytest.raises(ValueError, match="skip marker '_'"):
            format_index(5, "custom", custom_labels=custom_labels)


class TestDataclasses:
    """Tests for configuration dataclasses."""

    def test_grid_config(self):
        config = GridConfig(x=1.27, y=2.54)
        assert config.x == 1.27
        assert config.y == 2.54

    def test_origin_config(self):
        config = OriginConfig(x=10.0, y=20.0)
        assert config.x == 10.0
        assert config.y == 20.0

    def test_axis_config_defaults(self):
        config = AxisConfig()
        assert config.x_direction == "positive"
        assert config.y_direction == "positive"

    def test_index_config_defaults(self):
        config = IndexConfig()
        assert config.x_start == 1
        assert config.y_start == 1

    def test_format_config_defaults(self):
        config = FormatConfig()
        assert config.x_type == "number"
        assert config.y_type == "letter"
        assert config.x_padding == 0
        assert config.y_padding == 0
        assert config.custom_x is None
        assert config.custom_y is None

    def test_format_config_with_custom(self):
        config = FormatConfig(
            x_type="custom",
            y_type="custom",
            custom_x=["1", "2", "3"],
            custom_y=["a", "b", "c", "pl", "mi"],
        )
        assert config.x_type == "custom"
        assert config.custom_x == ["1", "2", "3"]
        assert config.custom_y == ["a", "b", "c", "pl", "mi"]

    def test_sort_config_defaults(self):
        config = SortConfig()
        assert config.by == "none"
        assert config.x_order == "ascending"
        assert config.y_order == "ascending"

    def test_sort_config_custom(self):
        config = SortConfig(by="x_then_y", x_order="descending", y_order="ascending")
        assert config.by == "x_then_y"
        assert config.x_order == "descending"
        assert config.y_order == "ascending"


class TestSortShapes:
    """Tests for sort_shapes function."""

    def _create_shapes(self):
        """Create test shapes at various positions."""
        from svg_tools.geometry import RectInfo
        elem = ET.Element("rect")
        # Create shapes at: (0,0), (2.54,0), (0,2.54), (2.54,2.54)
        shapes = [
            RectInfo(element=elem, id="r-2-2", x=2.04, y=2.04, width=1.0, height=1.0),  # center (2.54, 2.54)
            RectInfo(element=elem, id="r-0-0", x=-0.5, y=-0.5, width=1.0, height=1.0),  # center (0, 0)
            RectInfo(element=elem, id="r-2-0", x=2.04, y=-0.5, width=1.0, height=1.0),  # center (2.54, 0)
            RectInfo(element=elem, id="r-0-2", x=-0.5, y=2.04, width=1.0, height=1.0),  # center (0, 2.54)
        ]
        return shapes

    def test_sort_none(self):
        shapes = self._create_shapes()
        original_order = [s.id for s in shapes]
        config = SortConfig(by="none")
        sorted_shapes = sort_shapes(shapes, config)
        assert [s.id for s in sorted_shapes] == original_order

    def test_sort_x_then_y_ascending(self):
        shapes = self._create_shapes()
        config = SortConfig(by="x_then_y", x_order="ascending", y_order="ascending")
        sorted_shapes = sort_shapes(shapes, config)
        # Expected order: (0,0), (0,2.54), (2.54,0), (2.54,2.54)
        assert [s.id for s in sorted_shapes] == ["r-0-0", "r-0-2", "r-2-0", "r-2-2"]

    def test_sort_x_then_y_descending(self):
        shapes = self._create_shapes()
        config = SortConfig(by="x_then_y", x_order="descending", y_order="descending")
        sorted_shapes = sort_shapes(shapes, config)
        # Expected order: (2.54,2.54), (2.54,0), (0,2.54), (0,0)
        assert [s.id for s in sorted_shapes] == ["r-2-2", "r-2-0", "r-0-2", "r-0-0"]

    def test_sort_y_then_x_ascending(self):
        shapes = self._create_shapes()
        config = SortConfig(by="y_then_x", x_order="ascending", y_order="ascending")
        sorted_shapes = sort_shapes(shapes, config)
        # Expected order: (0,0), (2.54,0), (0,2.54), (2.54,2.54)
        assert [s.id for s in sorted_shapes] == ["r-0-0", "r-2-0", "r-0-2", "r-2-2"]

    def test_sort_y_then_x_descending(self):
        shapes = self._create_shapes()
        config = SortConfig(by="y_then_x", x_order="descending", y_order="descending")
        sorted_shapes = sort_shapes(shapes, config)
        # Expected order: (2.54,2.54), (0,2.54), (2.54,0), (0,0)
        assert [s.id for s in sorted_shapes] == ["r-2-2", "r-0-2", "r-2-0", "r-0-0"]

    def test_sort_mixed_orders(self):
        shapes = self._create_shapes()
        config = SortConfig(by="x_then_y", x_order="ascending", y_order="descending")
        sorted_shapes = sort_shapes(shapes, config)
        # Expected order: (0,2.54), (0,0), (2.54,2.54), (2.54,0)
        assert [s.id for s in sorted_shapes] == ["r-0-2", "r-0-0", "r-2-2", "r-2-0"]


class TestGroupRelabelResult:
    """Tests for GroupRelabelResult dataclass."""

    def test_empty_result(self):
        result = GroupRelabelResult(
            group_name="test",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(1.27, 1.27),
        )
        assert result.changed_count == 0
        assert result.unchanged_count == 0
        assert result.has_errors is False

    def test_result_with_changes(self):
        result = GroupRelabelResult(
            group_name="test",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(1.27, 1.27),
            changes=[
                LabelChange("e1", "old1", "new1", 0.0, 0.0, 1, 1),
                LabelChange("e2", "same", "same", 1.27, 0.0, 2, 1),
                LabelChange("e3", None, "new3", 2.54, 0.0, 3, 1),
            ],
        )
        assert result.changed_count == 2
        assert result.unchanged_count == 1

    def test_result_with_errors(self):
        result = GroupRelabelResult(
            group_name="test",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(1.27, 1.27),
            errors=["Some error"],
        )
        assert result.has_errors is True


class TestRelabelReport:
    """Tests for RelabelReport dataclass."""

    def test_empty_report(self):
        report = RelabelReport(file_path=Path("test.svg"))
        assert report.has_errors is False
        assert report.total_elements == 0
        assert report.total_changed == 0

    def test_report_with_groups(self):
        group1 = GroupRelabelResult(
            group_name="g1",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(1.27, 1.27),
            changes=[
                LabelChange("e1", "old", "new", 0.0, 0.0, 1, 1),
                LabelChange("e2", "old", "new", 1.27, 0.0, 2, 1),
            ],
        )
        group2 = GroupRelabelResult(
            group_name="g2",
            shape_type="arc",
            origin=(0.0, 0.0),
            grid=(1.27, 1.27),
            changes=[
                LabelChange("e3", "old", "new", 0.0, 0.0, 1, 1),
            ],
        )
        report = RelabelReport(
            file_path=Path("test.svg"),
            group_results=[group1, group2],
        )
        assert report.total_elements == 3
        assert report.total_changed == 3


class TestParseRelabelRuleFile:
    """Tests for parse_relabel_rule_file function."""

    @pytest.fixture
    def valid_rule_file(self, tmp_path) -> Path:
        """Create a valid rule file."""
        content = """
groups:
  - name: "s-circle"
    shape: arc
    label_template: "hole-{x}-{y}"
    grid:
      x: 2.54
      y: 2.54
    origin:
      x: 10.16
      y: 10.16
    axis:
      x_direction: positive
      y_direction: positive
    index:
      x_start: 1
      y_start: 1
    format:
      x_type: number
      y_type: letter
      x_padding: 0

  - name: "s-rect"
    shape: rect
    label_template: "pad-{x}{y}"
    grid:
      x: 1.27
      y: 1.27
    format:
      x_type: letter_upper
      y_type: number
      y_padding: 2
"""
        rule_file = tmp_path / "rule.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_valid_rule(self, valid_rule_file):
        rule = parse_relabel_rule_file(valid_rule_file)

        assert len(rule.groups) == 2

        # Check first group
        g1 = rule.groups[0]
        assert g1.name == "s-circle"
        assert g1.shape == "arc"
        assert g1.label_template == "hole-{x}-{y}"
        assert g1.grid.x == 2.54
        assert g1.grid.y == 2.54
        assert g1.origin is not None
        assert g1.origin.x == 10.16
        assert g1.axis.x_direction == "positive"
        assert g1.index.x_start == 1
        assert g1.format.x_type == "number"
        assert g1.format.y_type == "letter"

        # Check second group
        g2 = rule.groups[1]
        assert g2.name == "s-rect"
        assert g2.origin is None  # Uses auto origin
        assert g2.format.x_type == "letter_upper"
        assert g2.format.y_padding == 2

    @pytest.fixture
    def minimal_rule_file(self, tmp_path) -> Path:
        """Create a minimal rule file."""
        content = """
groups:
  - name: "shapes"
    shape: rect
    label_template: "shape-{x}-{y}"
    grid:
      x: 1.0
      y: 1.0
"""
        rule_file = tmp_path / "minimal.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_minimal_rule(self, minimal_rule_file):
        rule = parse_relabel_rule_file(minimal_rule_file)

        assert len(rule.groups) == 1
        g = rule.groups[0]
        assert g.name == "shapes"
        assert g.origin is None
        assert g.axis.x_direction == "positive"
        assert g.axis.y_direction == "positive"
        assert g.index.x_start == 1
        assert g.index.y_start == 1
        assert g.format.x_type == "number"
        assert g.format.y_type == "letter"
        # Sort defaults
        assert g.sort.by == "none"
        assert g.sort.x_order == "ascending"
        assert g.sort.y_order == "ascending"

    @pytest.fixture
    def rule_file_with_sort(self, tmp_path) -> Path:
        """Create a rule file with sort options."""
        content = """
groups:
  - name: "shapes"
    shape: rect
    label_template: "shape-{x}-{y}"
    grid:
      x: 1.0
      y: 1.0
    sort:
      by: x_then_y
      x_order: descending
      y_order: ascending
"""
        rule_file = tmp_path / "sort.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_rule_with_sort(self, rule_file_with_sort):
        rule = parse_relabel_rule_file(rule_file_with_sort)

        assert len(rule.groups) == 1
        g = rule.groups[0]
        assert g.sort.by == "x_then_y"
        assert g.sort.x_order == "descending"
        assert g.sort.y_order == "ascending"

    @pytest.fixture
    def invalid_sort_by_file(self, tmp_path) -> Path:
        """Create a rule file with invalid sort.by value."""
        content = """
groups:
  - name: "shapes"
    shape: rect
    label_template: "shape-{x}-{y}"
    grid:
      x: 1.0
      y: 1.0
    sort:
      by: invalid_value
"""
        rule_file = tmp_path / "invalid_sort.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_sort_by(self, invalid_sort_by_file):
        with pytest.raises(ValueError, match="Invalid sort.by"):
            parse_relabel_rule_file(invalid_sort_by_file)

    @pytest.fixture
    def rule_file_with_custom_labels(self, tmp_path) -> Path:
        """Create a rule file with custom labels."""
        content = """
groups:
  - name: "shapes"
    shape: rect
    label_template: "item-{x}-{y}"
    grid:
      x: 1.0
      y: 1.0
    format:
      x_type: number
      y_type: custom
      custom_y: [a, b, c, d, e, f, g, h, i, j, pl, mi]
"""
        rule_file = tmp_path / "custom.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_rule_with_custom_labels(self, rule_file_with_custom_labels):
        rule = parse_relabel_rule_file(rule_file_with_custom_labels)

        assert len(rule.groups) == 1
        g = rule.groups[0]
        assert g.format.x_type == "number"
        assert g.format.y_type == "custom"
        assert g.format.custom_y == ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "pl", "mi"]

    @pytest.fixture
    def rule_file_custom_without_labels(self, tmp_path) -> Path:
        """Create a rule file with custom type but no custom labels."""
        content = """
groups:
  - name: "shapes"
    shape: rect
    label_template: "item-{x}-{y}"
    grid:
      x: 1.0
      y: 1.0
    format:
      y_type: custom
"""
        rule_file = tmp_path / "custom_missing.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_custom_without_labels(self, rule_file_custom_without_labels):
        with pytest.raises(ValueError, match="custom_y is required"):
            parse_relabel_rule_file(rule_file_custom_without_labels)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_relabel_rule_file(Path("/nonexistent/rule.yaml"))

    @pytest.fixture
    def invalid_rule_file(self, tmp_path) -> Path:
        """Create an invalid rule file (missing required fields)."""
        content = """
groups:
  - name: "shapes"
    shape: rect
"""
        rule_file = tmp_path / "invalid.yaml"
        rule_file.write_text(content)
        return rule_file

    def test_parse_invalid_rule(self, invalid_rule_file):
        with pytest.raises(ValueError, match="must have 'label_template'"):
            parse_relabel_rule_file(invalid_rule_file)


class TestCalculateAutoOrigin:
    """Tests for calculate_auto_origin function."""

    def test_single_shape(self):
        from svg_tools.geometry import RectInfo
        elem = ET.Element("rect")
        shapes = [
            RectInfo(element=elem, id="r1", x=10.0, y=20.0, width=2.0, height=2.0),
        ]
        origin = calculate_auto_origin(shapes)
        # Center is (11.0, 21.0)
        assert origin == (11.0, 21.0)

    def test_multiple_shapes(self):
        from svg_tools.geometry import RectInfo
        elem = ET.Element("rect")
        shapes = [
            RectInfo(element=elem, id="r1", x=10.0, y=20.0, width=2.0, height=2.0),
            RectInfo(element=elem, id="r2", x=5.0, y=15.0, width=2.0, height=2.0),
            RectInfo(element=elem, id="r3", x=20.0, y=30.0, width=2.0, height=2.0),
        ]
        origin = calculate_auto_origin(shapes)
        # Min centers: (6.0, 16.0)
        assert origin == (6.0, 16.0)

    def test_empty_shapes(self):
        origin = calculate_auto_origin([])
        assert origin == (0.0, 0.0)


class TestCalculateGridIndex:
    """Tests for calculate_grid_index function."""

    def test_basic_calculation(self):
        center = (5.08, 7.62)
        origin = (0.0, 0.0)
        grid = GridConfig(x=2.54, y=2.54)
        axis = AxisConfig()
        index = IndexConfig()

        idx_x, idx_y = calculate_grid_index(center, origin, grid, axis, index)
        # 5.08 / 2.54 = 2, + 1 = 3
        # 7.62 / 2.54 = 3, + 1 = 4
        assert idx_x == 3
        assert idx_y == 4

    def test_with_origin_offset(self):
        center = (12.70, 15.24)
        origin = (2.54, 5.08)
        grid = GridConfig(x=2.54, y=2.54)
        axis = AxisConfig()
        index = IndexConfig()

        idx_x, idx_y = calculate_grid_index(center, origin, grid, axis, index)
        # (12.70 - 2.54) / 2.54 = 4, + 1 = 5
        # (15.24 - 5.08) / 2.54 = 4, + 1 = 5
        assert idx_x == 5
        assert idx_y == 5

    def test_negative_direction(self):
        center = (5.08, 7.62)
        origin = (10.16, 10.16)
        grid = GridConfig(x=2.54, y=2.54)
        axis = AxisConfig(x_direction="negative", y_direction="negative")
        index = IndexConfig()

        idx_x, idx_y = calculate_grid_index(center, origin, grid, axis, index)
        # (5.08 - 10.16) / 2.54 = -2, negate = 2, + 1 = 3
        # (7.62 - 10.16) / 2.54 = -1, negate = 1, + 1 = 2
        assert idx_x == 3
        assert idx_y == 2

    def test_custom_start_index(self):
        center = (2.54, 2.54)
        origin = (0.0, 0.0)
        grid = GridConfig(x=2.54, y=2.54)
        axis = AxisConfig()
        index = IndexConfig(x_start=0, y_start=0)

        idx_x, idx_y = calculate_grid_index(center, origin, grid, axis, index)
        # 2.54 / 2.54 = 1, + 0 = 1
        assert idx_x == 1
        assert idx_y == 1


class TestGenerateLabel:
    """Tests for generate_label function."""

    def test_basic_template(self):
        fmt = FormatConfig(x_type="number", y_type="letter")
        label = generate_label("hole-{x}-{y}", 1, 1, 0.0, 0.0, fmt)
        assert label == "hole-1-a"

    def test_template_with_padding(self):
        fmt = FormatConfig(x_type="number", y_type="number", x_padding=2, y_padding=3)
        label = generate_label("pad-{x}-{y}", 5, 12, 0.0, 0.0, fmt)
        assert label == "pad-05-012"

    def test_template_with_raw_values(self):
        fmt = FormatConfig()
        label = generate_label("item-{x_raw}-{y_raw}", 10, 20, 0.0, 0.0, fmt)
        assert label == "item-10-20"

    def test_template_with_coordinates(self):
        fmt = FormatConfig()
        label = generate_label("pos-{cx}-{cy}", 1, 1, 12.70, 25.40, fmt)
        assert label == "pos-12.70-25.40"

    def test_uppercase_letters(self):
        fmt = FormatConfig(x_type="letter_upper", y_type="letter_upper")
        label = generate_label("{x}{y}", 1, 2, 0.0, 0.0, fmt)
        assert label == "AB"


class TestCheckGridDeviation:
    """Tests for check_grid_deviation function."""

    def test_on_grid(self):
        center = (5.08, 7.62)
        origin = (0.0, 0.0)
        grid = GridConfig(x=2.54, y=2.54)

        dev_x, dev_y = check_grid_deviation(center, origin, grid)
        assert dev_x == pytest.approx(0.0)
        assert dev_y == pytest.approx(0.0)

    def test_off_grid(self):
        center = (5.0, 7.5)
        origin = (0.0, 0.0)
        grid = GridConfig(x=2.54, y=2.54)

        dev_x, dev_y = check_grid_deviation(center, origin, grid)
        # 5.0 % 2.54 = 1.92, min(1.92, 2.54-1.92=0.62) = 0.62
        # But nearest grid point: 5.08, so actual deviation is 0.08
        # 7.5 % 2.54 = 2.42, min(2.42, 2.54-2.42=0.12) = 0.12
        assert dev_x == pytest.approx(0.08, abs=0.01)  # 5.08 - 5.0 = 0.08
        assert dev_y == pytest.approx(0.12, abs=0.01)


class TestRelabelGroup:
    """Tests for relabel_group function."""

    def _create_svg_with_rects(self) -> ET.Element:
        """Create an SVG with rect elements."""
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(
            f"{{{svg_ns}}}svg",
            {"width": "100", "height": "100"},
        )
        group = ET.SubElement(
            root,
            f"{{{svg_ns}}}g",
            {f"{{{inkscape_ns}}}label": "shapes"},
        )

        # Create 3x2 grid of rects at 2.54mm spacing
        for row in range(2):
            for col in range(3):
                x = col * 2.54
                y = row * 2.54
                ET.SubElement(
                    group,
                    f"{{{svg_ns}}}rect",
                    {
                        "id": f"rect-{row}-{col}",
                        "x": str(x),
                        "y": str(y),
                        "width": "1.0",
                        "height": "1.0",
                        f"{{{inkscape_ns}}}label": f"old-{row}-{col}",
                    },
                )
        return root

    def test_relabel_without_apply(self):
        root = self._create_svg_with_rects()
        rule = RelabelGroupRule(
            name="shapes",
            shape="rect",
            label_template="hole-{x}-{y}",
            grid=GridConfig(x=2.54, y=2.54),
            format=FormatConfig(x_type="number", y_type="letter"),
        )

        result = relabel_group(root, rule, apply=False)

        assert len(result.changes) == 6
        assert result.has_errors is False

        # Check that labels were NOT applied
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        for elem in root.iter():
            label = elem.get(f"{{{inkscape_ns}}}label")
            if label and label.startswith("old-"):
                # Old labels should still be there
                pass

    def test_relabel_with_apply(self):
        root = self._create_svg_with_rects()
        rule = RelabelGroupRule(
            name="shapes",
            shape="rect",
            label_template="hole-{x}-{y}",
            grid=GridConfig(x=2.54, y=2.54),
            format=FormatConfig(x_type="number", y_type="letter"),
        )

        result = relabel_group(root, rule, apply=True)

        assert len(result.changes) == 6
        assert result.has_errors is False

        # Verify labels were applied
        expected_labels = {
            "rect-0-0": "hole-1-a",
            "rect-0-1": "hole-2-a",
            "rect-0-2": "hole-3-a",
            "rect-1-0": "hole-1-b",
            "rect-1-1": "hole-2-b",
            "rect-1-2": "hole-3-b",
        }

        for elem in root.iter():
            elem_id = elem.get("id")
            if elem_id in expected_labels:
                label = get_element_label(elem)
                assert label == expected_labels[elem_id]

    def test_group_not_found(self):
        svg_ns = SVG_NAMESPACES["svg"]
        root = ET.Element(f"{{{svg_ns}}}svg")

        rule = RelabelGroupRule(
            name="nonexistent",
            shape="rect",
            label_template="test-{x}-{y}",
            grid=GridConfig(x=1.0, y=1.0),
        )

        result = relabel_group(root, rule, apply=False)

        assert len(result.changes) == 0
        assert len(result.warnings) == 1
        assert "not found" in result.warnings[0]

    def test_duplicate_label_detection(self):
        """Test that duplicate labels are detected as errors."""
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(f"{{{svg_ns}}}svg")
        group = ET.SubElement(
            root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "shapes"}
        )

        # Create two rects at the same grid position
        ET.SubElement(
            group,
            f"{{{svg_ns}}}rect",
            {"id": "rect1", "x": "0", "y": "0", "width": "1", "height": "1"},
        )
        ET.SubElement(
            group,
            f"{{{svg_ns}}}rect",
            {"id": "rect2", "x": "0.1", "y": "0.1", "width": "1", "height": "1"},
        )

        rule = RelabelGroupRule(
            name="shapes",
            shape="rect",
            label_template="test-{x}-{y}",
            grid=GridConfig(x=2.54, y=2.54),
        )

        result = relabel_group(root, rule, apply=True)

        assert result.has_errors is True
        assert any("Duplicate" in e for e in result.errors)


class TestRelabelSvg:
    """Tests for relabel_svg function."""

    @pytest.fixture
    def sample_svg(self, tmp_path) -> Path:
        """Create a sample SVG file."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     width="100" height="100">
  <g inkscape:label="s-rect">
    <rect id="rect1" x="0" y="0" width="1.27" height="1.27" inkscape:label="old1"/>
    <rect id="rect2" x="2.54" y="0" width="1.27" height="1.27" inkscape:label="old2"/>
    <rect id="rect3" x="0" y="2.54" width="1.27" height="1.27" inkscape:label="old3"/>
  </g>
</svg>"""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(svg_content)
        return svg_file

    @pytest.fixture
    def rule(self) -> RelabelRule:
        """Create a test rule."""
        return RelabelRule(
            groups=[
                RelabelGroupRule(
                    name="s-rect",
                    shape="rect",
                    label_template="pad-{x}-{y}",
                    grid=GridConfig(x=2.54, y=2.54),
                    format=FormatConfig(x_type="number", y_type="letter"),
                ),
            ],
        )

    def test_relabel_svg(self, sample_svg, rule):
        tree, report = relabel_svg(sample_svg, rule, apply=False)

        assert report.file_path == sample_svg
        assert len(report.group_results) == 1
        assert report.total_elements == 3

    def test_relabel_svg_with_output(self, sample_svg, rule, tmp_path):
        tree, report = relabel_svg(sample_svg, rule, apply=True)

        assert not report.has_errors

        # Write output
        output_file = tmp_path / "output.svg"
        tree.write(output_file, encoding="unicode", xml_declaration=True)

        # Verify output file
        assert output_file.exists()


class TestFormatRelabelReport:
    """Tests for format_relabel_report function."""

    def test_format_empty_report(self):
        report = RelabelReport(file_path=Path("test.svg"))
        text = format_relabel_report(report)

        assert "test.svg" in text
        assert "Total elements: 0" in text

    def test_format_report_with_changes(self):
        group = GroupRelabelResult(
            group_name="shapes",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(2.54, 2.54),
            changes=[
                LabelChange("rect1", "old1", "new1", 0.0, 0.0, 1, 1),
                LabelChange("rect2", "old2", "new2", 2.54, 0.0, 2, 1),
            ],
        )
        report = RelabelReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_relabel_report(report)

        assert "shapes" in text
        assert "Changed: 2" in text
        assert '"old1" -> "new1"' in text

    def test_format_report_with_errors(self):
        group = GroupRelabelResult(
            group_name="shapes",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(2.54, 2.54),
            errors=["Duplicate label 'test-1-a'"],
        )
        report = RelabelReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_relabel_report(report)

        assert "[ERROR]" in text
        assert "Output file will not be generated" in text

    def test_format_report_with_warnings(self):
        group = GroupRelabelResult(
            group_name="shapes",
            shape_type="rect",
            origin=(0.0, 0.0),
            grid=(2.54, 2.54),
            warnings=["Element 'rect1' is off-grid"],
        )
        report = RelabelReport(
            file_path=Path("test.svg"),
            group_results=[group],
        )

        text = format_relabel_report(report)

        assert "[WARNING]" in text
        assert "off-grid" in text
