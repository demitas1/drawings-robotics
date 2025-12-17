"""Tests for svg_tools.process module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.process import (
    ProcessRule,
    ProcessReport,
    parse_process_rule_file,
    parse_align_section,
    parse_relabel_section,
    parse_add_text_section,
    process_svg,
    process_svg_tree,
    format_process_report,
    ALL_STEPS,
)
from svg_tools.align import AlignmentRule, ToleranceConfig
from svg_tools.relabel import RelabelRule
from svg_tools.add_text import AddTextRule
from svg_tools.utils import register_namespaces


class TestProcessRule:
    """Tests for ProcessRule dataclass."""

    def test_empty_rule(self):
        rule = ProcessRule()
        assert rule.align is None
        assert rule.relabel is None
        assert rule.add_text is None

    def test_with_align_only(self):
        rule = ProcessRule(align=AlignmentRule())
        assert rule.align is not None
        assert rule.relabel is None
        assert rule.add_text is None


class TestProcessReport:
    """Tests for ProcessReport dataclass."""

    def test_empty_report(self):
        report = ProcessReport(file_path=Path("test.svg"))
        assert report.has_errors is False
        assert report.executed_steps == []
        assert report.skipped_steps == []

    def test_has_errors_from_align(self):
        from svg_tools.align import AlignmentReport, GroupValidationResult, ValidationResult, Issue

        align_report = AlignmentReport(
            file_path=Path("test.svg"),
            group_results=[
                GroupValidationResult(
                    group_name="test",
                    shape_type="rect",
                    element_results=[
                        ValidationResult(
                            element_id="test-1",
                            shape_type="rect",
                            issues=[
                                Issue(
                                    element_id="test-1",
                                    field="width",
                                    status="error",
                                    actual=1.0,
                                    expected=2.0,
                                    deviation=1.0,
                                    message="error",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        report = ProcessReport(file_path=Path("test.svg"), align_report=align_report)
        assert report.has_errors is True

    def test_executed_steps(self):
        from svg_tools.align import AlignmentReport
        from svg_tools.relabel import RelabelReport

        report = ProcessReport(
            file_path=Path("test.svg"),
            align_report=AlignmentReport(file_path=Path("")),
            relabel_report=RelabelReport(file_path=Path("")),
        )
        assert report.executed_steps == ["align", "relabel"]


class TestParseAlignSection:
    """Tests for parse_align_section."""

    def test_empty_section(self):
        result = parse_align_section({})
        assert isinstance(result, AlignmentRule)
        assert len(result.groups) == 0

    def test_with_tolerance(self):
        data = {
            "tolerance": {
                "acceptable": 0.01,
                "error_threshold": 0.2,
            }
        }
        result = parse_align_section(data)
        assert result.tolerance.acceptable == 0.01
        assert result.tolerance.error_threshold == 0.2

    def test_with_groups(self):
        data = {
            "groups": [
                {
                    "name": "test",
                    "shape": "rect",
                    "grid": {"x": 1.27, "y": 1.27},
                }
            ]
        }
        result = parse_align_section(data)
        assert len(result.groups) == 1
        assert result.groups[0].name == "test"
        assert result.groups[0].shape == "rect"


class TestParseRelabelSection:
    """Tests for parse_relabel_section."""

    def test_empty_section(self):
        result = parse_relabel_section({})
        assert isinstance(result, RelabelRule)
        assert len(result.groups) == 0

    def test_with_group(self):
        data = {
            "groups": [
                {
                    "name": "test",
                    "shape": "arc",
                    "label_template": "hole-{x}-{y}",
                    "grid": {"x": 2.54, "y": 2.54},
                }
            ]
        }
        result = parse_relabel_section(data)
        assert len(result.groups) == 1
        assert result.groups[0].name == "test"
        assert result.groups[0].label_template == "hole-{x}-{y}"


class TestParseAddTextSection:
    """Tests for parse_add_text_section."""

    def test_empty_section(self):
        result = parse_add_text_section({})
        assert isinstance(result, AddTextRule)
        assert len(result.groups) == 0

    def test_horizontal_layout(self):
        data = {
            "groups": [
                {
                    "name": "test",
                    "y": 5.0,
                    "x_start": 0.0,
                    "x_end": 10.0,
                    "x_interval": 2.0,
                }
            ]
        }
        result = parse_add_text_section(data)
        assert len(result.groups) == 1
        assert result.groups[0].is_horizontal is True

    def test_vertical_layout(self):
        data = {
            "groups": [
                {
                    "name": "test",
                    "x": 5.0,
                    "y_start": 0.0,
                    "y_end": 10.0,
                    "y_interval": 2.0,
                }
            ]
        }
        result = parse_add_text_section(data)
        assert len(result.groups) == 1
        assert result.groups[0].is_vertical is True


class TestParseProcessRuleFile:
    """Tests for parse_process_rule_file."""

    def test_parse_complete_file(self):
        yaml_content = """
align:
  groups:
    - name: "s-rect"
      shape: rect
      grid: {x: 1.27, y: 1.27}
  tolerance:
    acceptable: 0.001

relabel:
  groups:
    - name: "s-circle"
      shape: arc
      label_template: "hole-{x}"
      grid: {x: 2.54, y: 2.54}

add_text:
  groups:
    - name: "labels"
      y: 5.0
      x_start: 0.0
      x_end: 10.0
      x_interval: 2.0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            rule = parse_process_rule_file(Path(f.name))

        assert rule.align is not None
        assert rule.relabel is not None
        assert rule.add_text is not None

    def test_parse_partial_file(self):
        yaml_content = """
align:
  groups:
    - name: "test"
      shape: rect
      grid: {x: 1.0, y: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            rule = parse_process_rule_file(Path(f.name))

        assert rule.align is not None
        assert rule.relabel is None
        assert rule.add_text is None


class TestProcessSvgTree:
    """Tests for process_svg_tree."""

    def create_test_tree(self) -> ET.ElementTree:
        """Create a minimal SVG tree for testing."""
        register_namespaces()
        svg = ET.Element("{http://www.w3.org/2000/svg}svg")
        svg.set("width", "100mm")
        svg.set("height", "100mm")
        svg.set("viewBox", "0 0 100 100")
        return ET.ElementTree(svg)

    def test_empty_rule_skips_all(self):
        tree = self.create_test_tree()
        rule = ProcessRule()
        report = process_svg_tree(tree, rule)

        assert len(report.skipped_steps) == 3
        assert "align (no rule)" in report.skipped_steps
        assert "relabel (no rule)" in report.skipped_steps
        assert "add_text (no rule)" in report.skipped_steps

    def test_step_filtering(self):
        tree = self.create_test_tree()
        rule = ProcessRule()
        report = process_svg_tree(tree, rule, steps=["align"])

        # Only align step, relabel and add_text not requested
        assert "align (no rule)" in report.skipped_steps
        assert "relabel (not requested)" in report.skipped_steps
        assert "add_text (not requested)" in report.skipped_steps


class TestFormatProcessReport:
    """Tests for format_process_report."""

    def test_format_empty_report(self):
        report = ProcessReport(file_path=Path("test.svg"))
        output = format_process_report(report)

        assert "File: test.svg" in output
        assert "SUMMARY" in output

    def test_format_with_skipped_steps(self):
        report = ProcessReport(
            file_path=Path("test.svg"),
            skipped_steps=["align (no rule)", "relabel (not requested)"],
        )
        output = format_process_report(report)

        assert "Skipped steps:" in output
        assert "align (no rule)" in output


class TestAllSteps:
    """Tests for ALL_STEPS constant."""

    def test_all_steps_order(self):
        assert ALL_STEPS == ["align", "relabel", "add_text"]

    def test_all_steps_immutable(self):
        steps_copy = list(ALL_STEPS)
        assert steps_copy == ["align", "relabel", "add_text"]
