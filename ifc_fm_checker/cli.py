#!/usr/bin/env python3
"""
ifc-fm-checker — CLI entry point

Usage:
  ifc-fm-checker path/to/model.ifc
  ifc-fm-checker model.ifc --output-dir ./reports --format html
  ifc-fm-checker model.ifc --folder ./project_files --format both
  ifc-fm-checker model.ifc --format json --verbose
"""

import argparse
import sys
import os

from ifc_fm_checker import __version__
from ifc_fm_checker.runner import run_all_checks
from ifc_fm_checker.config import RATING_COLORS


def _color(text: str, code: str) -> str:
    """Apply ANSI color code if stdout is a terminal."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _score_color(score: int) -> str:
    if score >= 85:
        return _color(str(score), "32")   # green
    elif score >= 70:
        return _color(str(score), "33")   # yellow
    elif score >= 50:
        return _color(str(score), "91")   # orange
    return _color(str(score), "31")       # red


def main():
    parser = argparse.ArgumentParser(
        prog="ifc-fm-checker",
        description=(
            "IFC FM Readiness Checker — "
            "Verify if an IFC model is ready for CAFM/CMMS import.\n"
            "Checks: Spatial Structure, Pset Completeness, Asset Data, "
            "COBie Readiness, ISO 19650 File Naming."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ifc-fm-checker building.ifc\n"
            "  ifc-fm-checker building.ifc --format both --output-dir ./reports\n"
            "  ifc-fm-checker building.ifc --folder ./project --verbose\n"
        ),
    )

    parser.add_argument("ifc_file", help="Path to the IFC file to check")
    parser.add_argument(
        "--folder", "-f",
        metavar="FOLDER_PATH",
        help="Optional: folder path to also validate ISO 19650 file naming",
        default=None,
    )
    parser.add_argument(
        "--output-dir", "-o",
        metavar="OUTPUT_DIR",
        help="Directory for output reports (default: same folder as IFC file)",
        default=None,
    )
    parser.add_argument(
        "--format",
        choices=["html", "json", "both"],
        default="html",
        help="Output format: html (default), json, or both",
    )
    parser.add_argument(
        "--ids",
        metavar="IDS_FILE",
        help="Optional: path to a buildingSMART IDS (.ids) file for additional validation",
        default=None,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ifc-fm-checker {__version__}",
    )

    args = parser.parse_args()

    # Header
    print()
    print(_color("━" * 60, "34"))
    print(_color("  IFC FM Readiness Checker", "1") + f"  v{__version__}")
    print(_color("━" * 60, "34"))
    print(f"  File   : {os.path.basename(args.ifc_file)}")
    if args.folder:
        print(f"  Folder : {args.folder}")
    if args.ids:
        print(f"  IDS    : {os.path.basename(args.ids)}")
    print(f"  Format : {args.format}")
    print()

    try:
        result = run_all_checks(
            ifc_path=args.ifc_file,
            folder_path=args.folder,
            ids_path=args.ids,
            output_dir=args.output_dir,
            output_format=args.format,
            verbose=args.verbose,
        )
    except FileNotFoundError as e:
        print(_color(f"  ✖  Error: {e}", "31"))
        sys.exit(1)
    except Exception as e:
        print(_color(f"  ✖  Unexpected error: {e}", "31"))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Print per-check scores
    print(_color("  Check Results", "1"))
    print(_color("  " + "─" * 56, "90"))

    check_labels = {
        "spatial_structure": "Spatial Structure    (15%)",
        "pset_completeness":  "Pset Completeness   (25%)",
        "asset_data":         "Asset Data          (30%)",
        "cobie_readiness":    "COBie Readiness     (20%)",
        "file_naming":        "File Naming ISO 19650(10%)",
        "ids_validation":     "IDS Validation       (opt)",
        "system_assignment":  "MEP Systems           (info)",
    }

    for check in result["results"]:
        key = check.get("check_key", "")
        label = check_labels.get(key, check["name"])
        score = check["score"]
        n_issues = len([i for i in check.get("issues", []) if i.get("severity") in ("error", "warning")])
        issue_str = f"  {n_issues} issue(s)" if n_issues else _color("  ✓ OK", "32")
        bar = _build_bar(score)
        print(f"  {label:<30} {_score_color(score):>3}/100  {bar} {issue_str}")

    print(_color("  " + "─" * 56, "90"))

    # Overall score
    score = result["overall_score"]
    rating = result["rating"]
    print()
    print(f"  Overall Score  : {_score_color(score)}/100")
    print(f"  FM Readiness   : {_color(rating, '1')}")
    print()

    if result.get("output_file"):
        print(f"  Report saved to: {_color(result['output_file'], '36')}")
    print(_color("━" * 60, "34"))
    print()

    # Exit code: 0 if FM READY or MOSTLY READY, 1 otherwise (useful for CI)
    sys.exit(0 if score >= 70 else 1)


def _build_bar(score: int, width: int = 12) -> str:
    filled = int(score / 100 * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    if score >= 85:
        return _color(f"[{bar}]", "32")
    elif score >= 70:
        return _color(f"[{bar}]", "33")
    elif score >= 50:
        return _color(f"[{bar}]", "91")
    return _color(f"[{bar}]", "31")


if __name__ == "__main__":
    main()
