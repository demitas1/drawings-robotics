#!/usr/bin/env python3
"""Validate and align SVG shapes according to specified rules."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.align import (
    AlignmentReport,
    format_report,
    parse_rule_file,
    validate_svg,
)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error, 2 for validation errors).
    """
    parser = argparse.ArgumentParser(
        description="Validate and align SVG shapes according to specified rules."
    )
    parser.add_argument("svg_file", type=Path, help="Path to SVG file to process")
    parser.add_argument(
        "--rule", "-r", type=Path, required=True, help="Path to YAML rule file"
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output SVG file (enables fixing)"
    )

    args = parser.parse_args()

    # Validate input files exist
    if not args.svg_file.exists():
        print(f"Error: SVG file not found: {args.svg_file}", file=sys.stderr)
        return 1

    if not args.rule.exists():
        print(f"Error: Rule file not found: {args.rule}", file=sys.stderr)
        return 1

    # Parse rule file
    try:
        rule = parse_rule_file(args.rule)
    except Exception as e:
        print(f"Error: Failed to parse rule file: {e}", file=sys.stderr)
        return 1

    # Validate (and optionally fix)
    fix = args.output is not None
    try:
        tree, report = validate_svg(args.svg_file, rule, fix=fix)
    except Exception as e:
        print(f"Error: Failed to process SVG: {e}", file=sys.stderr)
        return 1

    # Print report
    print(format_report(report))

    # Handle output
    if args.output:
        if report.has_errors:
            print(
                f"\nError: Cannot write output due to errors above.",
                file=sys.stderr,
            )
            return 2
        else:
            try:
                tree.write(args.output, encoding="unicode", xml_declaration=True)
                print(f"\nOutput written to: {args.output}")
            except Exception as e:
                print(f"Error: Failed to write output: {e}", file=sys.stderr)
                return 1

    return 0 if not report.has_errors else 2


if __name__ == "__main__":
    sys.exit(main())
