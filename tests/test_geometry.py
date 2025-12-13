"""Tests for svg_tools.geometry module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES
from svg_tools.geometry import (
    BoundingBox,
    RectInfo,
    ArcInfo,
    PathInfo,
    parse_rect,
    parse_arc,
    parse_path,
    parse_shape,
    snap_to_grid,
    check_grid_alignment,
    check_value_match,
    update_rect,
    update_arc,
    update_path,
)


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_center_x(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        assert bbox.center_x == 60  # 10 + 100/2

    def test_center_y(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        assert bbox.center_y == 45  # 20 + 50/2

    def test_center(self):
        bbox = BoundingBox(x=0, y=0, width=10, height=20)
        assert bbox.center == (5, 10)

    def test_zero_size(self):
        bbox = BoundingBox(x=5, y=5, width=0, height=0)
        assert bbox.center == (5, 5)


class TestRectInfo:
    """Tests for RectInfo dataclass."""

    def test_bbox(self):
        elem = ET.Element("rect")
        info = RectInfo(element=elem, id="test", x=10, y=20, width=30, height=40)
        bbox = info.bbox
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 30
        assert bbox.height == 40

    def test_center(self):
        elem = ET.Element("rect")
        info = RectInfo(element=elem, id="test", x=0, y=0, width=10, height=20)
        assert info.center == (5, 10)


class TestArcInfo:
    """Tests for ArcInfo dataclass."""

    def test_bbox(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem, id="test", cx=10, cy=20, rx=5, ry=10, start=0, end=6.28
        )
        bbox = info.bbox
        assert bbox.x == 5  # cx - rx
        assert bbox.y == 10  # cy - ry
        assert bbox.width == 10  # rx * 2
        assert bbox.height == 20  # ry * 2

    def test_center(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem, id="test", cx=50, cy=100, rx=5, ry=5, start=0, end=6.28
        )
        assert info.center == (50, 100)

    def test_arc_span(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem, id="test", cx=0, cy=0, rx=1, ry=1, start=0, end=3.14
        )
        assert info.arc_span == pytest.approx(3.14)

    def test_arc_span_negative(self):
        elem = ET.Element("path")
        info = ArcInfo(
            element=elem, id="test", cx=0, cy=0, rx=1, ry=1, start=3.14, end=0
        )
        assert info.arc_span == pytest.approx(3.14)


class TestParseRect:
    """Tests for parse_rect function."""

    def test_valid_rect(self):
        svg_ns = SVG_NAMESPACES["svg"]
        elem = ET.Element(
            f"{{{svg_ns}}}rect",
            {"id": "rect-001", "x": "10.5", "y": "20.5", "width": "30", "height": "40"},
        )
        info = parse_rect(elem)
        assert info is not None
        assert info.id == "rect-001"
        assert info.x == 10.5
        assert info.y == 20.5
        assert info.width == 30
        assert info.height == 40

    def test_rect_without_namespace(self):
        elem = ET.Element(
            "rect", {"id": "rect-002", "x": "5", "y": "5", "width": "10", "height": "10"}
        )
        info = parse_rect(elem)
        assert info is not None
        assert info.id == "rect-002"

    def test_rect_default_values(self):
        elem = ET.Element("rect", {"id": "rect-003"})
        info = parse_rect(elem)
        assert info is not None
        assert info.x == 0
        assert info.y == 0
        assert info.width == 0
        assert info.height == 0

    def test_non_rect_element(self):
        elem = ET.Element("circle", {"id": "circle-001"})
        info = parse_rect(elem)
        assert info is None

    def test_invalid_numeric_values(self):
        elem = ET.Element("rect", {"x": "invalid", "y": "10"})
        info = parse_rect(elem)
        assert info is None


class TestParseArc:
    """Tests for parse_arc function."""

    def test_valid_arc(self):
        svg_ns = SVG_NAMESPACES["svg"]
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            f"{{{svg_ns}}}path",
            {
                "id": "arc-001",
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}cx": "50.5",
                f"{{{sodipodi_ns}}}cy": "100.5",
                f"{{{sodipodi_ns}}}rx": "10",
                f"{{{sodipodi_ns}}}ry": "20",
                f"{{{sodipodi_ns}}}start": "0",
                f"{{{sodipodi_ns}}}end": "6.28",
            },
        )
        info = parse_arc(elem)
        assert info is not None
        assert info.id == "arc-001"
        assert info.cx == 50.5
        assert info.cy == 100.5
        assert info.rx == 10
        assert info.ry == 20
        assert info.start == 0
        assert info.end == 6.28

    def test_non_arc_path(self):
        svg_ns = SVG_NAMESPACES["svg"]
        elem = ET.Element(f"{{{svg_ns}}}path", {"id": "path-001", "d": "M0,0 L10,10"})
        info = parse_arc(elem)
        assert info is None

    def test_non_path_element(self):
        elem = ET.Element("rect", {"id": "rect-001"})
        info = parse_arc(elem)
        assert info is None

    def test_arc_default_values(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element("path", {f"{{{sodipodi_ns}}}type": "arc"})
        info = parse_arc(elem)
        assert info is not None
        assert info.cx == 0
        assert info.cy == 0
        assert info.rx == 0
        assert info.ry == 0


class TestParseShape:
    """Tests for parse_shape function."""

    def test_parse_rect_shape(self):
        elem = ET.Element("rect", {"id": "rect-001", "x": "10", "y": "20", "width": "30", "height": "40"})
        info = parse_shape(elem, "rect")
        assert info is not None
        assert isinstance(info, RectInfo)

    def test_parse_arc_shape(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                "id": "arc-001",
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}cx": "50",
                f"{{{sodipodi_ns}}}cy": "50",
            },
        )
        info = parse_shape(elem, "arc")
        assert info is not None
        assert isinstance(info, ArcInfo)

    def test_wrong_shape_type(self):
        elem = ET.Element("rect", {"id": "rect-001"})
        info = parse_shape(elem, "arc")
        assert info is None


class TestSnapToGrid:
    """Tests for snap_to_grid function."""

    def test_exact_multiple(self):
        assert snap_to_grid(5.08, 1.27) == pytest.approx(5.08)

    def test_snap_up(self):
        assert snap_to_grid(5.1, 1.27) == pytest.approx(5.08)

    def test_snap_down(self):
        assert snap_to_grid(5.0, 1.27) == pytest.approx(5.08)

    def test_zero(self):
        assert snap_to_grid(0, 1.27) == 0

    def test_negative_value(self):
        assert snap_to_grid(-2.54, 1.27) == pytest.approx(-2.54)

    def test_small_grid(self):
        assert snap_to_grid(0.5, 0.1) == pytest.approx(0.5)


class TestCheckGridAlignment:
    """Tests for check_grid_alignment function."""

    def test_aligned(self):
        aligned, deviation = check_grid_alignment(5.08, 1.27, 0.001)
        assert aligned is True
        assert deviation < 0.001

    def test_not_aligned(self):
        aligned, deviation = check_grid_alignment(5.1, 1.27, 0.001)
        assert aligned is False
        assert deviation > 0.001

    def test_within_tolerance(self):
        aligned, deviation = check_grid_alignment(5.0805, 1.27, 0.001)
        assert aligned is True

    def test_at_tolerance_boundary(self):
        # 5.081 - 5.08 = 0.001, which is at the boundary
        aligned, deviation = check_grid_alignment(5.0805, 1.27, 0.001)
        assert aligned is True

    def test_deviation_near_grid_unit(self):
        # Value is 1.2695 which is 0.0005 away from 1.27
        aligned, deviation = check_grid_alignment(1.2695, 1.27, 0.001)
        assert aligned is True
        assert deviation == pytest.approx(0.0005)


class TestCheckValueMatch:
    """Tests for check_value_match function."""

    def test_within_tolerance(self):
        status, deviation = check_value_match(1.27, 1.27, 0.001, 0.1)
        assert status == "ok"

    def test_within_tolerance_boundary(self):
        status, deviation = check_value_match(1.2705, 1.27, 0.001, 0.1)
        assert status == "ok"

    def test_fixable(self):
        status, deviation = check_value_match(1.28, 1.27, 0.001, 0.1)
        assert status == "fixable"
        assert deviation == pytest.approx(0.01)

    def test_error(self):
        status, deviation = check_value_match(1.5, 1.27, 0.001, 0.1)
        assert status == "error"

    def test_error_threshold_boundary(self):
        # 10% of 1.27 is 0.127, so 1.397 should be error
        status, deviation = check_value_match(1.4, 1.27, 0.001, 0.1)
        assert status == "error"

    def test_zero_expected(self):
        status, deviation = check_value_match(0.5, 0, 0.001, 0.1)
        assert status == "error"  # 0.5 > 0.1 absolute


class TestUpdateRect:
    """Tests for update_rect function."""

    def test_update_x(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, x=15.5)
        assert elem.get("x") == "15.5"
        assert elem.get("y") == "20"  # unchanged

    def test_update_y(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, y=25.5)
        assert elem.get("y") == "25.5"

    def test_update_width(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, width=35)
        assert elem.get("width") == "35"

    def test_update_height(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, height=45)
        assert elem.get("height") == "45"

    def test_update_multiple(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, x=5, y=10, width=20, height=30)
        assert elem.get("x") == "5"
        assert elem.get("y") == "10"
        assert elem.get("width") == "20"
        assert elem.get("height") == "30"

    def test_update_none_keeps_original(self):
        elem = ET.Element("rect", {"x": "10", "y": "20", "width": "30", "height": "40"})
        update_rect(elem, x=None, y=None)
        assert elem.get("x") == "10"
        assert elem.get("y") == "20"


class TestUpdateArc:
    """Tests for update_arc function."""

    def test_update_cx(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}cx": "50",
                f"{{{sodipodi_ns}}}cy": "50",
            },
        )
        update_arc(elem, cx=60.5)
        assert elem.get(f"{{{sodipodi_ns}}}cx") == "60.5"
        assert elem.get(f"{{{sodipodi_ns}}}cy") == "50"  # unchanged

    def test_update_cy(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {f"{{{sodipodi_ns}}}type": "arc", f"{{{sodipodi_ns}}}cy": "50"},
        )
        update_arc(elem, cy=70.5)
        assert elem.get(f"{{{sodipodi_ns}}}cy") == "70.5"

    def test_update_rx_ry(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}rx": "10",
                f"{{{sodipodi_ns}}}ry": "10",
            },
        )
        update_arc(elem, rx=15, ry=20)
        assert elem.get(f"{{{sodipodi_ns}}}rx") == "15"
        assert elem.get(f"{{{sodipodi_ns}}}ry") == "20"

    def test_update_start_end(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                f"{{{sodipodi_ns}}}type": "arc",
                f"{{{sodipodi_ns}}}start": "0",
                f"{{{sodipodi_ns}}}end": "3.14",
            },
        )
        update_arc(elem, start=0.5, end=6.28)
        assert elem.get(f"{{{sodipodi_ns}}}start") == "0.5"
        assert elem.get(f"{{{sodipodi_ns}}}end") == "6.28"

    def test_update_none_keeps_original(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {f"{{{sodipodi_ns}}}type": "arc", f"{{{sodipodi_ns}}}cx": "50"},
        )
        update_arc(elem, cx=None)
        assert elem.get(f"{{{sodipodi_ns}}}cx") == "50"


class TestPathInfo:
    """Tests for PathInfo dataclass."""

    def test_bbox(self):
        elem = ET.Element("path")
        info = PathInfo(
            element=elem,
            id="path-001",
            start_x=10.0,
            start_y=20.0,
            end_x=30.0,
            end_y=40.0,
        )
        bbox = info.bbox
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 20.0
        assert bbox.height == 20.0

    def test_center(self):
        elem = ET.Element("path")
        info = PathInfo(
            element=elem,
            id="path-001",
            start_x=0.0,
            start_y=0.0,
            end_x=10.0,
            end_y=20.0,
        )
        assert info.center == (5.0, 10.0)

    def test_is_vertical(self):
        elem = ET.Element("path")
        info = PathInfo(
            element=elem,
            id="path-001",
            start_x=5.08,
            start_y=5.08,
            end_x=5.08,
            end_y=17.78,
        )
        assert info.is_vertical is True
        assert info.is_horizontal is False

    def test_is_horizontal(self):
        elem = ET.Element("path")
        info = PathInfo(
            element=elem,
            id="path-001",
            start_x=5.08,
            start_y=45.72,
            end_x=78.74,
            end_y=45.72,
        )
        assert info.is_vertical is False
        assert info.is_horizontal is True


class TestParsePath:
    """Tests for parse_path function."""

    def test_vertical_path_absolute(self):
        elem = ET.Element("path", {"id": "path-001", "d": "M 5.08,5.08 V 17.78"})
        info = parse_path(elem)
        assert info is not None
        assert info.id == "path-001"
        assert info.start_x == pytest.approx(5.08)
        assert info.start_y == pytest.approx(5.08)
        assert info.end_x == pytest.approx(5.08)
        assert info.end_y == pytest.approx(17.78)

    def test_horizontal_path_absolute(self):
        elem = ET.Element("path", {"id": "path-002", "d": "M 5.08,45.72 H 78.74"})
        info = parse_path(elem)
        assert info is not None
        assert info.start_x == pytest.approx(5.08)
        assert info.start_y == pytest.approx(45.72)
        assert info.end_x == pytest.approx(78.74)
        assert info.end_y == pytest.approx(45.72)

    def test_lineto_path_absolute(self):
        elem = ET.Element("path", {"id": "path-003", "d": "M 0,0 L 10,20"})
        info = parse_path(elem)
        assert info is not None
        assert info.start_x == 0.0
        assert info.start_y == 0.0
        assert info.end_x == 10.0
        assert info.end_y == 20.0

    def test_relative_moveto_horizontal(self):
        elem = ET.Element("path", {"id": "path-004", "d": "m 45.72,48.26 h 33.02"})
        info = parse_path(elem)
        assert info is not None
        assert info.start_x == pytest.approx(45.72)
        assert info.start_y == pytest.approx(48.26)
        assert info.end_x == pytest.approx(78.74)
        assert info.end_y == pytest.approx(48.26)

    def test_relative_vertical(self):
        elem = ET.Element("path", {"id": "path-005", "d": "M 5.08,5.08 v 12.7"})
        info = parse_path(elem)
        assert info is not None
        assert info.start_x == pytest.approx(5.08)
        assert info.start_y == pytest.approx(5.08)
        assert info.end_x == pytest.approx(5.08)
        assert info.end_y == pytest.approx(17.78)

    def test_arc_path_returns_none(self):
        sodipodi_ns = SVG_NAMESPACES["sodipodi"]
        elem = ET.Element(
            "path",
            {
                "id": "arc-001",
                "d": "...",
                f"{{{sodipodi_ns}}}type": "arc",
            },
        )
        info = parse_path(elem)
        assert info is None

    def test_non_path_element(self):
        elem = ET.Element("rect", {"id": "rect-001"})
        info = parse_path(elem)
        assert info is None

    def test_empty_d_attribute(self):
        elem = ET.Element("path", {"id": "path-001", "d": ""})
        info = parse_path(elem)
        assert info is None


class TestParseShapePath:
    """Tests for parse_shape function with path type."""

    def test_parse_path_shape(self):
        elem = ET.Element("path", {"id": "path-001", "d": "M 5.08,5.08 V 17.78"})
        info = parse_shape(elem, "path")
        assert info is not None
        assert isinstance(info, PathInfo)

    def test_wrong_shape_type_for_path(self):
        elem = ET.Element("path", {"id": "path-001", "d": "M 5.08,5.08 V 17.78"})
        info = parse_shape(elem, "rect")
        assert info is None


class TestUpdatePath:
    """Tests for update_path function."""

    def test_update_vertical_path(self):
        elem = ET.Element("path", {"id": "path-001", "d": "M 5.08,5.08 V 17.78"})
        update_path(elem, start_x=5.1, start_y=5.1, end_x=5.1, end_y=17.8)
        d = elem.get("d")
        assert "M 5.1,5.1" in d
        assert "V 17.8" in d

    def test_update_horizontal_path(self):
        elem = ET.Element("path", {"id": "path-002", "d": "M 5.08,45.72 H 78.74"})
        update_path(elem, end_x=80.0)
        d = elem.get("d")
        assert "H 80.0" in d

    def test_update_diagonal_path(self):
        elem = ET.Element("path", {"id": "path-003", "d": "M 0,0 L 10,20"})
        update_path(elem, end_x=15.0, end_y=25.0)
        d = elem.get("d")
        assert "L 15.0,25.0" in d

    def test_update_none_keeps_original(self):
        elem = ET.Element("path", {"id": "path-001", "d": "M 5.08,5.08 V 17.78"})
        update_path(elem)
        d = elem.get("d")
        assert "5.08" in d
        assert "17.78" in d
