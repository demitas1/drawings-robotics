#!/usr/bin/env python3
"""Analyze SVG files and display element statistics by group."""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVGStats, GroupStats, analyze_svg, iter_all_groups


def format_table(stats: SVGStats) -> str:
    """Format statistics as a text table.

    Args:
        stats: SVG statistics to format.

    Returns:
        Formatted table string.
    """
    lines = []
    lines.append(f"File: {stats.file_path}")
    lines.append(f"Total elements: {stats.total_elements}")
    lines.append("")

    # Build table rows
    rows: list[tuple[str, str, str]] = []
    rows.append(("Group", "Elements", "Count"))
    rows.append(("-" * 30, "-" * 20, "-" * 8))

    for group in iter_all_groups(stats):
        indent = "  " * group.depth
        group_name = f"{indent}{group.name}"

        if group.element_counts:
            first = True
            for elem_type, count in sorted(group.element_counts.items()):
                if first:
                    rows.append((group_name, elem_type, str(count)))
                    first = False
                else:
                    rows.append(("", elem_type, str(count)))
            # Add subtotal if multiple element types
            if len(group.element_counts) > 1:
                rows.append(("", "(subtotal)", str(group.total_elements)))
        else:
            rows.append((group_name, "(empty)", "0"))

    # Add ungrouped elements
    if stats.ungrouped_counts:
        rows.append(("-" * 30, "-" * 20, "-" * 8))
        first = True
        for elem_type, count in sorted(stats.ungrouped_counts.items()):
            if first:
                rows.append(("(ungrouped)", elem_type, str(count)))
                first = False
            else:
                rows.append(("", elem_type, str(count)))

    # Calculate column widths
    col_widths = [
        max(len(row[0]) for row in rows),
        max(len(row[1]) for row in rows),
        max(len(row[2]) for row in rows),
    ]

    # Format rows
    for row in rows:
        line = f"{row[0]:<{col_widths[0]}}  {row[1]:<{col_widths[1]}}  {row[2]:>{col_widths[2]}}"
        lines.append(line)

    return "\n".join(lines)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Analyze SVG files and display element statistics by group."
    )
    parser.add_argument("svg_file", type=Path, help="Path to SVG file to analyze")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    if not args.svg_file.exists():
        print(f"Error: File not found: {args.svg_file}", file=sys.stderr)
        return 1

    try:
        stats = analyze_svg(args.svg_file)
    except Exception as e:
        print(f"Error: Failed to parse SVG: {e}", file=sys.stderr)
        return 1

    if args.format == "json":
        output = json.dumps(stats.to_dict(), indent=2, ensure_ascii=False)
    else:
        output = format_table(stats)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
