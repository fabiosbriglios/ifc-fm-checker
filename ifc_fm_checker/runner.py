"""
Core runner — orchestrates all checks and produces the final report.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

import ifcopenshell

from ifc_fm_checker.config import SCORING_WEIGHTS
from ifc_fm_checker.utils import get_authoring_tool, get_schema
from ifc_fm_checker.checks import check_spatial, check_psets, check_assets, check_cobie, check_naming, check_ids, check_systems, check_clashes
from ifc_fm_checker.report import html_report


def run_all_checks(
    ifc_path: str,
    folder_path: Optional[str] = None,
    ids_path: Optional[str] = None,
    tolerance_cm: float = 0.0,
    output_dir: Optional[str] = None,
    output_format: str = "html",
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Main entry point. Loads the IFC file, runs all checks, and produces the report.

    Returns a dict with:
        overall_score, rating, model_info, results (per check), output_file
    """
    ifc_path = str(ifc_path)

    if not os.path.exists(ifc_path):
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")

    if verbose:
        print(f"  Loading {os.path.basename(ifc_path)}...")

    ifc_file = ifcopenshell.open(ifc_path)

    # --- Gather model metadata ---
    model_info = _get_model_info(ifc_file, ifc_path)

    if verbose:
        print(f"  Schema: {model_info['schema']} | Tool: {model_info['authoring_tool']}")
        print(f"  Elements: {model_info['total_elements']}")

    # --- Run checks ---
    results = []

    checks = [
        ("spatial_structure", check_spatial.run, [ifc_file], {}),
        ("pset_completeness",  check_psets.run,   [ifc_file], {}),
        ("asset_data",         check_assets.run,  [ifc_file], {}),
        ("cobie_readiness",    check_cobie.run,   [ifc_file], {}),
        ("file_naming",        check_naming.run,
            [ifc_file],
            {"file_path": ifc_path, "folder_path": folder_path}),
        # IDS validation — optional, does not affect FM Readiness score
        ("ids_validation",     check_ids.run,
            [ifc_file],
            {"ids_path": ids_path}),
        # MEP system assignment — informational (weight=0.0 in v1.1)
        ("system_assignment",  check_systems.run, [ifc_file], {}),
        # Geometric clash detection — informational (weight=0.0)
        ("clash_detection",    check_clashes.run, [ifc_file], {"tolerance_cm": tolerance_cm}),
    ]

    for check_key, check_fn, args, kwargs in checks:
        if verbose:
            print(f"  Running: {check_key}...")
        try:
            result = check_fn(*args, **kwargs)
            result["check_key"] = check_key
            results.append(result)
        except Exception as e:
            results.append({
                "name": check_key,
                "check_key": check_key,
                "score": 0,
                "issues": [{
                    "severity": "error",
                    "element": "Runner",
                    "message": f"Check failed with error: {e}",
                    "fix": "Report this issue at https://github.com/fabio-sbriglio/ifc-fm-checker/issues",
                }],
                "stats": {},
                "description": f"Check '{check_key}' could not be completed.",
            })

    # --- Compute weighted overall score ---
    overall_score = 0
    for result in results:
        key = result.get("check_key", "")
        weight = SCORING_WEIGHTS.get(key, 0)
        overall_score += result["score"] * weight
    overall_score = int(overall_score)

    # --- Determine rating ---
    from ifc_fm_checker.config import RATING_THRESHOLDS, RATING_LABELS
    if overall_score >= RATING_THRESHOLDS["excellent"]:
        rating = "FM READY"
    elif overall_score >= RATING_THRESHOLDS["good"]:
        rating = "MOSTLY READY"
    elif overall_score >= RATING_THRESHOLDS["fair"]:
        rating = "NEEDS WORK"
    else:
        rating = "NOT READY"

    # --- Generate output ---
    if output_dir is None:
        output_dir = os.path.dirname(ifc_path) or "."

    stem = Path(ifc_path).stem
    output_file = None

    if output_format in ("html", "both"):
        html_path = os.path.join(output_dir, f"{stem}_fm_report.html")
        html_report.render(results, overall_score, model_info, html_path)
        output_file = html_path
        if verbose:
            print(f"  HTML report: {html_path}")

    if output_format in ("json", "both"):
        json_path = os.path.join(output_dir, f"{stem}_fm_report.json")
        json_data = {
            "overall_score": overall_score,
            "rating": rating,
            "model_info": model_info,
            "checks": results,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, default=str)
        if output_file is None:
            output_file = json_path
        if verbose:
            print(f"  JSON report: {json_path}")

    return {
        "overall_score": overall_score,
        "rating": rating,
        "model_info": model_info,
        "results": results,
        "output_file": output_file,
    }


def _get_model_info(ifc_file, ifc_path: str) -> Dict[str, Any]:
    """Collect model metadata for the report header."""
    schema = get_schema(ifc_file)
    tool = get_authoring_tool(ifc_file)

    # Count elements
    element_counts = {}
    for etype in [
        "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcDoor", "IfcWindow",
        "IfcSpace", "IfcBuildingStorey", "IfcFlowTerminal", "IfcFlowSegment",
    ]:
        n = len(ifc_file.by_type(etype))
        if n > 0:
            element_counts[etype] = n

    total = len(ifc_file.by_type("IfcProduct"))

    # Project name
    project_name = "Unknown"
    try:
        projects = ifc_file.by_type("IfcProject")
        if projects:
            project_name = projects[0].Name or "Unknown"
    except Exception:
        pass

    return {
        "filename": os.path.basename(ifc_path),
        "file_path": ifc_path,
        "schema": schema,
        "authoring_tool": tool,
        "project_name": project_name,
        "total_elements": total,
        "element_summary": ", ".join(f"{v} {k[3:]}" for k, v in element_counts.items()),
    }
