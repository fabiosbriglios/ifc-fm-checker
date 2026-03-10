"""
Check 2: Pset Completeness
Verifies that required property sets and their properties are present
and filled for each relevant IFC element type.
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.config import REQUIRED_PSETS
from ifc_fm_checker.utils import get_psets, prop_is_filled, get_entity_label


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}
    type_scores = {}

    total_checks = 0
    passed_checks = 0

    for ifc_type, pset_requirements in REQUIRED_PSETS.items():
        elements = ifc_file.by_type(ifc_type)
        if not elements:
            continue

        type_pass = 0
        type_total = 0
        type_issues = []

        for element in elements:
            psets = get_psets(element)

            for pset_name, required_props in pset_requirements.items():
                actual_pset = psets.get(pset_name, {})

                for prop in required_props:
                    type_total += 1
                    total_checks += 1

                    value = actual_pset.get(prop, None)

                    if pset_name not in psets:
                        # Entire Pset missing
                        type_issues.append({
                            "severity": "error",
                            "element": get_entity_label(element),
                            "message": f"Pset '{pset_name}' not found — property '{prop}' missing",
                            "fix": (
                                f"In Revit: assign '{pset_name}' to the type/instance. "
                                f"In IFC export: ensure Pset_Common export is enabled."
                            ),
                        })
                    elif prop not in actual_pset:
                        type_issues.append({
                            "severity": "error",
                            "element": get_entity_label(element),
                            "message": f"'{pset_name}.{prop}' property not found",
                            "fix": (
                                f"Add property '{prop}' to '{pset_name}'. "
                                f"Check IFC export settings in your authoring tool."
                            ),
                        })
                    elif not prop_is_filled(value):
                        type_issues.append({
                            "severity": "warning",
                            "element": get_entity_label(element),
                            "message": f"'{pset_name}.{prop}' is empty or null",
                            "fix": f"Fill in '{prop}' value for this element in the authoring tool.",
                        })
                    else:
                        type_pass += 1
                        passed_checks += 1

        # Deduplicate: group issues by message (show counts)
        deduplicated = _deduplicate_issues(type_issues)
        issues.extend(deduplicated)

        score = int(type_pass / type_total * 100) if type_total > 0 else 100
        type_scores[ifc_type] = {
            "score": score,
            "total_elements": len(elements),
            "checks_passed": type_pass,
            "checks_total": type_total,
        }
        stats[ifc_type] = type_scores[ifc_type]

    overall_score = int(passed_checks / total_checks * 100) if total_checks > 0 else 100

    return {
        "name": "Pset Completeness",
        "score": overall_score,
        "issues": issues,
        "stats": {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "by_type": type_scores,
        },
        "description": (
            "Checks that required Property Sets (Pset_WallCommon, "
            "Pset_SpaceCommon, Pset_ManufacturerTypeInformation, etc.) "
            "are present and filled according to ISO 19650 requirements."
        ),
    }


def _deduplicate_issues(issues):
    """Group repeated issues by message and count them."""
    seen = {}
    for issue in issues:
        key = issue["message"]
        if key not in seen:
            seen[key] = {**issue, "count": 1, "elements": [issue["element"]]}
        else:
            seen[key]["count"] += 1
            if len(seen[key]["elements"]) < 5:
                seen[key]["elements"].append(issue["element"])

    result = []
    for key, item in seen.items():
        if item["count"] > 1:
            item["element"] = (
                f"{item['elements'][0]}"
                + (f" and {item['count'] - 1} more" if item["count"] > 1 else "")
            )
            item["message"] = f"[×{item['count']}] {item['message']}"
        del item["elements"]
        del item["count"]
        result.append(item)

    return result
