#!/usr/bin/env python3
"""Process SVG files through unified pipeline (align -> relabel -> add_text)."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.process import (
    ALL_STEPS,
    StepName,
    format_process_report,
    parse_process_rule_file,
    process_svg,
)


def parse_steps(steps_arg: str | None) -> list[StepName]:
    """Parse steps argument.

    Args:
        steps_arg: Comma-separated step names or 'all'.

    Returns:
        List of step names to execute.

    Raises:
        ValueError: If invalid step name is provided.
    """
    if steps_arg is None or steps_arg.lower() == "all":
        return list(ALL_STEPS)

    steps: list[StepName] = []
    for step in steps_arg.split(","):
        step = step.strip().lower()
        if step not in ALL_STEPS:
            valid_steps = ", ".join(ALL_STEPS)
            raise ValueError(f"Invalid step '{step}'. Valid steps: {valid_steps}, all")
        steps.append(step)  # type: ignore

    return steps


def main() -> int:
    """Main entry point.

    Returns:
        Exit code:
        - 0: Success
        - 1: I/O error
        - 2: Rule file error
        - 3: Processing errors detected
    """
    parser = argparse.ArgumentParser(
        description="Process SVG files through unified pipeline (align -> relabel -> add_text).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate only (no output file)
  %(prog)s input.svg --rule rules.yaml

  # Process and save output
  %(prog)s input.svg --rule rules.yaml --output output.svg

  # Run specific steps only
  %(prog)s input.svg --rule rules.yaml --steps align,relabel --output output.svg

  # Dry run (preview changes without writing)
  %(prog)s input.svg --rule rules.yaml --output output.svg --dry-run
""",
    )
    parser.add_argument("svg_file", type=Path, help="Path to SVG file to process")
    parser.add_argument(
        "--rule", "-r", type=Path, required=True, help="Path to unified YAML rule file"
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output SVG file (enables processing)"
    )
    parser.add_argument(
        "--steps",
        "-s",
        type=str,
        default="all",
        help="Steps to execute: align,relabel,add_text or 'all' (default: all)",
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

    # Parse steps
    try:
        steps = parse_steps(args.steps)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Parse rule file
    try:
        rule = parse_process_rule_file(args.rule)
    except Exception as e:
        print(f"Error: Failed to parse rule file: {e}", file=sys.stderr)
        return 2

    # Determine if we should apply changes
    apply = args.output is not None and not args.dry_run

    # Process SVG
    try:
        tree, report = process_svg(args.svg_file, rule, steps=steps, apply=apply)
    except Exception as e:
        print(f"Error: Failed to process SVG: {e}", file=sys.stderr)
        return 1

    # Print report
    print(format_process_report(report))

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
