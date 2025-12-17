"""SVG Tools - Cross-platform SVG normalization and analysis utilities."""

__version__ = "0.1.0"

from .align import (
    AlignmentReport,
    AlignmentRule,
    parse_rule_file as parse_align_rule_file,
    validate_svg,
    validate_svg_tree,
)
from .relabel import (
    RelabelReport,
    RelabelRule,
    parse_relabel_rule_file,
    relabel_svg,
    relabel_svg_tree,
)
from .add_text import (
    AddTextReport,
    AddTextRule,
    parse_add_text_rule_file,
    add_text_to_svg,
    add_text_to_svg_tree,
)
from .process import (
    ProcessReport,
    ProcessRule,
    parse_process_rule_file,
    process_svg,
    process_svg_tree,
    format_process_report,
)

__all__ = [
    # Align
    "AlignmentReport",
    "AlignmentRule",
    "parse_align_rule_file",
    "validate_svg",
    "validate_svg_tree",
    # Relabel
    "RelabelReport",
    "RelabelRule",
    "parse_relabel_rule_file",
    "relabel_svg",
    "relabel_svg_tree",
    # Add text
    "AddTextReport",
    "AddTextRule",
    "parse_add_text_rule_file",
    "add_text_to_svg",
    "add_text_to_svg_tree",
    # Process (unified pipeline)
    "ProcessReport",
    "ProcessRule",
    "parse_process_rule_file",
    "process_svg",
    "process_svg_tree",
    "format_process_report",
]
