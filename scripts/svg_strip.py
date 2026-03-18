#!/usr/bin/env python3
"""Remove specified groups (layers) from SVG files by inkscape:label."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.strip import StripRule, format_strip_report, strip_svg


def main() -> int:
    """Main entry point.

    Returns:
        Exit code:
        - 0: Success
        - 1: I/O error
        - 2: Argument error
    """
    parser = argparse.ArgumentParser(
        description="Remove specified groups (layers) from SVG files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview which groups would be removed (dry run)
  %(prog)s input.svg --groups _ref

  # Remove groups and save output
  %(prog)s input.svg --groups _ref --output output.svg

  # Remove multiple groups
  %(prog)s input.svg --groups "_ref,guide" --output output.svg
""",
    )
    parser.add_argument("svg_file", type=Path, help="Path to SVG file to process")
    parser.add_argument(
        "--groups",
        "-g",
        type=str,
        required=True,
        help="Comma-separated list of inkscape:label values to remove",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output SVG file path (required to write changes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be removed without writing output",
    )

    args = parser.parse_args()

    if not args.svg_file.exists():
        print(f"Error: SVG file not found: {args.svg_file}", file=sys.stderr)
        return 1

    group_names = [name.strip() for name in args.groups.split(",") if name.strip()]
    if not group_names:
        print("Error: --groups must specify at least one group label", file=sys.stderr)
        return 2

    rule = StripRule(groups=group_names)

    try:
        tree, report = strip_svg(args.svg_file, rule)
    except Exception as e:
        print(f"Error: Failed to process SVG: {e}", file=sys.stderr)
        return 1

    print(f"File: {args.svg_file}")
    print()
    print(format_strip_report(report))

    if args.output and not args.dry_run:
        try:
            tree.write(args.output, encoding="unicode", xml_declaration=True)
            print(f"\nOutput written to: {args.output}")
        except Exception as e:
            print(f"Error: Failed to write output: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
