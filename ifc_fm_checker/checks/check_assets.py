"""
Check 3: Asset Data
Verifies that maintainable assets have the critical data fields
required for CAFM/CMMS import: AssetTag, Manufacturer, Model,
InstallationDate, WarrantyDuration.
"""

import ifcopenshell
from typing import Dict, Any, List
from ifc_fm_checker.config import ASSET_TYPES, ASSET_CRITICAL_PROPS
from ifc_fm_checker.utils import (
    get_all_props_including_type,
    prop_is_filled,
    get_entity_label,
    get_parent_storey,
)


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}

    asset_elements = []
    for asset_type in ASSET_TYPES:
        try:
            asset_elements.extend(ifc_file.by_type(asset_type))
        except RuntimeError:
            pass  # type not in this schema version

    if not asset_elements:
        return {
            "name": "Asset Data",
            "score": 100,
            "issues": [{
                "severity": "info",
                "element": "Model",
                "message": "No maintainable asset types found in this model",
                "fix": "If this is an architectural-only model, this check may not apply.",
            }],
            "stats": {"total_assets": 0},
            "description": "Checks CAFM-critical properties on maintainable equipment.",
        }

    stats["total_assets"] = len(asset_elements)
    field_results = {field: {"present": 0, "missing": 0} for field in ASSET_CRITICAL_PROPS}
    missing_by_field = {field: [] for field in ASSET_CRITICAL_PROPS}

    per_element_scores = []

    for element in asset_elements:
        all_props = get_all_props_including_type(element)
        label = get_entity_label(element)
        storey = get_parent_storey(element) or "Unknown"
        element_pass = 0

        for field_key, aliases in ASSET_CRITICAL_PROPS.items():
            found = False
            for alias in aliases:
                val = all_props.get(alias, None)
                if prop_is_filled(val):
                    found = True
                    break

            if found:
                field_results[field_key]["present"] += 1
                element_pass += 1
            else:
                field_results[field_key]["missing"] += 1
                missing_by_field[field_key].append({"label": label, "storey": storey})

        per_element_scores.append(element_pass / len(ASSET_CRITICAL_PROPS))

    # Build issues per field
    for field_key, missing_list in missing_by_field.items():
        if not missing_list:
            continue

        aliases = ASSET_CRITICAL_PROPS[field_key]
        pct = len(missing_list) / len(asset_elements) * 100
        severity = "error" if pct > 50 else "warning"

        sample = [m["label"] for m in missing_list[:3]]
        more = len(missing_list) - 3 if len(missing_list) > 3 else 0
        element_str = ", ".join(sample) + (f" and {more} more" if more else "")

        issues.append({
            "severity": severity,
            "element": element_str,
            "message": (
                f"[×{len(missing_list)}] Asset field '{field_key}' missing "
                f"({pct:.0f}% of {len(asset_elements)} assets) — "
                f"expected in: {', '.join(aliases)}"
            ),
            "fix": _get_fix(field_key),
        })

    # Score: average element completeness
    avg_score = int(sum(per_element_scores) / len(per_element_scores) * 100) if per_element_scores else 100

    # Build stats
    stats["field_coverage"] = {
        field: {
            "present": field_results[field]["present"],
            "missing": field_results[field]["missing"],
            "pct_complete": round(
                field_results[field]["present"] / len(asset_elements) * 100, 1
            ),
        }
        for field in ASSET_CRITICAL_PROPS
    }

    return {
        "name": "Asset Data",
        "score": avg_score,
        "issues": issues,
        "stats": stats,
        "description": (
            "Verifies that maintainable equipment has CAFM-critical fields: "
            "AssetTag/Mark, Manufacturer, ModelReference, InstallationDate, "
            "WarrantyDuration."
        ),
    }


def _get_fix(field_key: str) -> str:
    fixes = {
        "asset_code": (
            "In Revit: add an 'AssetTag' or 'Mark' shared parameter to the family. "
            "Fill values before IFC export. "
            "In ISO 19650: asset codes should follow the EIR classification system."
        ),
        "manufacturer": (
            "In Revit: fill 'Manufacturer' in the Type Properties of each family. "
            "In Archicad: fill 'Manufacturer' in the Component Properties."
        ),
        "model": (
            "In Revit: fill 'Model' in Type Properties. "
            "Ensure IFC export maps it to Pset_ManufacturerTypeInformation.ModelReference."
        ),
        "install_date": (
            "Add an 'InstallationDate' shared parameter to MEP families. "
            "For existing buildings: use the commissioning date or building completion year."
        ),
        "warranty": (
            "Add a 'WarrantyDuration' parameter (in months) to equipment families. "
            "Critical for CAFM preventive maintenance scheduling."
        ),
    }
    return fixes.get(field_key, "Fill in the required field in the authoring tool.")
