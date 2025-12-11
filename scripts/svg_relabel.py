#!/usr/bin/env python3
"""Relabel SVG shapes according to coordinate-based rules."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.relabel import (
    format_relabel_report,
    parse_relabel_rule_file,
    relabel_svg,
)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code:
        - 0: Success
        - 1: I/O error
        - 2: Rule file error
        - 3: Target group not found or errors detected
    """
    parser = argparse.ArgumentParser(
        description="Relabel SVG shapes according to coordinate-based rules."
    )
    parser.add_argument("svg_file", type=Path, help="Path to SVG file to process")
    parser.add_argument(
        "--rule", "-r", type=Path, required=True, help="Path to YAML rule file"
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output SVG file (enables relabeling)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing output",
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
        rule = parse_relabel_rule_file(args.rule)
    except Exception as e:
        print(f"Error: Failed to parse rule file: {e}", file=sys.stderr)
        return 2

    # Determine if we should apply changes
    apply = args.output is not None and not args.dry_run

    # Process SVG
    try:
        tree, report = relabel_svg(args.svg_file, rule, apply=apply)
    except Exception as e:
        print(f"Error: Failed to process SVG: {e}", file=sys.stderr)
        return 1

    # Print report
    print(format_relabel_report(report))

    # Handle output
    if args.output and not args.dry_run:
        if report.has_errors:
            print(
                f"\nError: Cannot write output due to errors above.",
                file=sys.stderr,
            )
            return 3
        else:
            try:
                tree.write(args.output, encoding="unicode", xml_declaration=True)
                print(f"\nOutput written to: {args.output}")
            except Exception as e:
                print(f"Error: Failed to write output: {e}", file=sys.stderr)
                return 1

    # Return appropriate exit code
    if report.has_errors:
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
